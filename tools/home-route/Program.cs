using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

// Aponta o botao Home da TV para o Kurumi Home e desfaz a mudanca.
//
// Roda na TV como uid 901(sdk), via /usr/bin/dotnet. As funcoes nativas sao as
// mesmas que o Couchroot usa no S90D:
//   - app_operation_set_current_app: grava a linha da operacao "main" no
//     /opt/dbspace/user/5001/.appsvc.db, que e o que o botao Home consulta.
//   - vconf_set_str/int: mantem db/appfw/home_appid e o autostart do Smart Hub,
//     que o app-boot-manager usa para abrir o app no boot.
class KurumiHomeControl
{
    const string Operation = "http://tizen.org/appcontrol/operation/main";
    const string Kurumi = "KurumiTV01.Home";
    const string SamsungHome = "com.samsung.tv.csfs";
    const string HomeKey = "db/appfw/home_appid";
    const string StartupKey = "db/appfw/startup_appid";
    const string BackupKey = "db/appfw/booting_appid_backup";
    const string AutoKey = "db/menu/smart_hub/ontvsetting/auto_start";

    [DllImport("libbundle.so.0")] static extern IntPtr bundle_create();
    [DllImport("libbundle.so.0")] static extern void bundle_free(IntPtr bundle);
    [DllImport("libaul.so.0")] static extern int aul_svc_set_operation(IntPtr bundle, string operation);
    [DllImport("libaul.so.0")] static extern int aul_get_default_app(IntPtr bundle, out IntPtr app);
    [DllImport("libcapi-appfw-app-operation-tv.so.0")]
    static extern int app_operation_set_current_app(string operation, string app);
    [DllImport("libvconf.so.0")] static extern int vconf_set_str(string key, string value);
    [DllImport("libvconf.so.0")] static extern IntPtr vconf_get_str(string key);
    [DllImport("libvconf.so.0")] static extern int vconf_set_int(string key, int value);
    [DllImport("libvconf.so.0")] static extern int vconf_get_int(string key, out int value);
    [DllImport("libc")] static extern uint getuid();
    [DllImport("libc")] static extern void free(IntPtr pointer);

    static string ReadString(string key)
    {
        IntPtr pointer = vconf_get_str(key);
        if (pointer == IntPtr.Zero) return null;
        try { return Marshal.PtrToStringAnsi(pointer); }
        finally { free(pointer); }
    }

    static void SetString(string key, string value)
    {
        if (value == null) return;
        if (vconf_set_str(key, value) != 0)
            throw new Exception("vconf_set_str falhou: " + key);
        string actual = ReadString(key);
        if (actual != value)
            throw new Exception("leitura de volta diferente em " + key + ": " + actual);
        Console.WriteLine(key + "=" + actual);
    }

    static int ReadInt(string key)
    {
        int value;
        if (vconf_get_int(key, out value) != 0)
            throw new Exception("vconf_get_int falhou: " + key);
        return value;
    }

    static void SetInt(string key, int value)
    {
        if (vconf_set_int(key, value) != 0)
            throw new Exception("vconf_set_int falhou: " + key);
        int actual = ReadInt(key);
        if (actual != value)
            throw new Exception("leitura de volta diferente em " + key + ": " + actual);
        Console.WriteLine(key + "=" + actual);
    }

    static string CurrentHome(IntPtr bundle)
    {
        IntPtr app;
        int result = aul_get_default_app(bundle, out app);
        string current = app == IntPtr.Zero ? null : Marshal.PtrToStringAnsi(app);
        if (app != IntPtr.Zero) free(app);
        if (result != 0)
            throw new Exception("aul_get_default_app falhou: " + result);
        return current;
    }

    static void SetHome(IntPtr bundle, string target)
    {
        string current = CurrentHome(bundle);
        if (current == target) return;
        int result = app_operation_set_current_app(Operation, target);
        Console.WriteLine("set_result=" + result + " alvo=" + target);
        if (result != 0)
            throw new Exception("app_operation_set_current_app falhou: " + result);
        string actual = CurrentHome(bundle);
        if (actual != target)
            throw new Exception("Home nao mudou para " + target + "; esta " + actual);
    }

    static void PrintSnapshot()
    {
        Console.WriteLine("stock.home_appid=" + (ReadString(HomeKey) ?? ""));
        Console.WriteLine("stock.startup_appid=" + (ReadString(StartupKey) ?? ""));
        Console.WriteLine("stock.booting_appid_backup=" + (ReadString(BackupKey) ?? ""));
        Console.WriteLine("stock.auto_start=" + ReadInt(AutoKey));
    }

    static int Main(string[] args)
    {
        try
        {
            if (IntPtr.Size != 4)
            {
                Console.Error.WriteLine("esperado runtime 32-bit; achado " + (IntPtr.Size * 8) + "-bit");
                return 2;
            }
            if (args.Length < 1)
            {
                Console.Error.WriteLine("uso: query | set | restore <home> <startup> <backup> <auto>");
                return 2;
            }
            string mode = args[0];
            Console.WriteLine("uid=" + getuid());
            if (mode == "query")
            {
                IntPtr probe = bundle_create();
                if (probe == IntPtr.Zero) return 3;
                try
                {
                    if (aul_svc_set_operation(probe, Operation) != 0) return 4;
                    Console.WriteLine("home_atual=" + (CurrentHome(probe) ?? "<nenhum>"));
                }
                finally { bundle_free(probe); }
                PrintSnapshot();
                return 0;
            }

            if (mode == "set")
            {
                IntPtr bundle = bundle_create();
                if (bundle == IntPtr.Zero) return 3;
                try
                {
                    if (aul_svc_set_operation(bundle, Operation) != 0) return 4;
                    string current = CurrentHome(bundle);
                    Console.WriteLine("home_atual=" + (current ?? "<nenhum>"));
                    if (current != SamsungHome && current != Kurumi)
                    {
                        Console.Error.WriteLine(
                            "Home atual inesperado (" + current + "); nada foi alterado.");
                        return 7;
                    }
                    PrintSnapshot();
                    SetHome(bundle, Kurumi);
                    SetString(HomeKey, Kurumi);
                    SetInt(AutoKey, 1);
                    Console.WriteLine("home_depois=" + (CurrentHome(bundle) ?? "<nenhum>"));
                    Console.WriteLine("startup=" + (ReadString(StartupKey) ?? "<nenhum>"));
                    return 0;
                }
                finally { bundle_free(bundle); }
            }

            if (mode == "update-query")
            {
                Console.WriteLine("autoupdate=" + ReadInt("db/menu/support/softwareupdate/autoupdate"));
                Console.WriteLine("preupdate_consent=" + ReadInt("db/menu/support/softwareupdate/preupdate_consent"));
                try
                {
                    Console.WriteLine("block_standby_scan=" + ReadInt("db/menu/support/softwareupdate/block_standby_scan"));
                }
                catch (Exception)
                {
                    Console.WriteLine("block_standby_scan=<ausente>");
                }
                return 0;
            }

            if (mode == "update-off" || mode == "update-on")
            {
                bool off = mode == "update-off";
                SetInt("db/menu/support/softwareupdate/autoupdate", off ? 0 : 1);
                SetInt("db/menu/support/softwareupdate/preupdate_consent", off ? 0 : 1);
                try
                {
                    SetInt("db/menu/support/softwareupdate/block_standby_scan", off ? 1 : 0);
                }
                catch (Exception error)
                {
                    // A chave pode nao existir nesta firmware. O autoupdate acima
                    // ja e o interruptor principal; reportamos sem falhar tudo.
                    Console.Error.WriteLine("aviso block_standby_scan: " + error.Message);
                }
                return 0;
            }

            if (mode == "restore")
            {
                if (args.Length != 6)
                {
                    Console.Error.WriteLine(
                        "restore precisa de: <home> <startup> <backup> <auto> <home_operation>");
                    return 2;
                }
                string home = args[1];
                string startup = args[2];
                string backup = args[3];
                int auto;
                if (!int.TryParse(args[4], out auto))
                {
                    Console.Error.WriteLine("auto_start invalido: " + args[4]);
                    return 2;
                }
                string homeOperation = args[5];
                if (homeOperation != SamsungHome && homeOperation != Kurumi)
                {
                    Console.Error.WriteLine("home_operation invalido: " + homeOperation);
                    return 2;
                }
                if (home != SamsungHome && home != Kurumi)
                {
                    Console.Error.WriteLine("home_appid invalido: " + home);
                    return 2;
                }

                IntPtr bundle = bundle_create();
                if (bundle == IntPtr.Zero) return 3;
                try
                {
                    if (aul_svc_set_operation(bundle, Operation) != 0) return 4;
                    SetHome(bundle, homeOperation);
                    SetString(HomeKey, home);
                    SetString(StartupKey, startup);
                    SetString(BackupKey, backup);
                    SetInt(AutoKey, auto);
                    Console.WriteLine("home_depois=" + (CurrentHome(bundle) ?? "<nenhum>"));
                    return 0;
                }
                finally { bundle_free(bundle); }
            }

            Console.Error.WriteLine("modo invalido: " + mode);
            return 2;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("erro: " + error.Message);
            return 1;
        }
    }
}
