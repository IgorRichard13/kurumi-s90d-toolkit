using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;

// Helper de boot do Kurumi Saver, chamado pelo AT-HUB via /usr/bin/dotnet.
// Ele preserva o diagnostico original (/opt/etc/parseinfo.sh) e faz um bind
// mount somente-leitura do ContentList.json do Kurumi sobre o do launcher de
// screensaver. Se algo nao bater, deixa o screensaver original intacto.
class Boot
{
    const string State = "/opt/minimal-saver";
    const string Stock = "/usr/apps/com.samsung.tv.glscreensaver-launcher/res/ContentList.json";
    const string Source = "/opt/minimal-saver/ContentList.json";
    const string OriginalHash = "23b0564a366e09fcba9592449d7fc8124480732980f9f6300daa60ee4ef08466";
    const string CustomHash = "e802155cd726aae2a32a137d7820d716c7265d22e5ebf641878e5d716ea5f430";
    const string DiagnosticHash = "c6369e7dec69408e176daa252d436acf6f8e265f560504d8bd831c8023c71d61";

    [DllImport("libc.so.6")] static extern uint geteuid();
    [DllImport("libc.so.6", SetLastError = true)]
    static extern int mount(string source, string target, string filesystem, UIntPtr flags, string data);
    [DllImport("libc.so.6", SetLastError = true)]
    static extern int umount2(string target, int flags);

    static string Hash(string file)
    {
        using var input = File.OpenRead(file);
        using var sha = SHA256.Create();
        return Convert.ToHexString(sha.ComputeHash(input)).ToLowerInvariant();
    }

    static void Require(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }

    static bool HasOverlay()
    {
        return File.ReadLines("/proc/self/mountinfo")
            .Any(line => line.Split(' ')[4] == Stock);
    }

    static void Mount(string source, ulong flags)
    {
        int result = mount(source, Stock, null, new UIntPtr(flags), null);
        Require(result == 0, "mount failed errno=" + Marshal.GetLastWin32Error());
    }

    static readonly string[] GuardUnits =
    {
        "com.samsung.tv.slive-daemon.service",
        "com.samsung.tv.slive-daemon.path",
        "slive-provider-daemon.service",
        "slive-provider-daemon.path",
        "slive-daemon.service",
        "slive-daemon.path",
        "com.samsung.tv.ghdaemon.service",
        "com.samsung.tv.ghdaemon.path",
        "ghdaemon.service",
        "mde-framework.service",
        "com.samsung.tv.mde-framework.service"
    };

    static void Run(string file, Action<string> log, params string[] arguments)
    {
        try
        {
            var start = new ProcessStartInfo(file) { UseShellExecute = false };
            foreach (string argument in arguments) start.ArgumentList.Add(argument);
            using var process = Process.Start(start);
            if (process == null)
            {
                log("command failed to start: " + file);
                return;
            }
            if (!process.WaitForExit(10000))
            {
                process.Kill(true);
                log("command timed out: " + file + " " + string.Join(" ", arguments));
                return;
            }
            if (process.ExitCode != 0)
                log("command exit " + process.ExitCode + ": " + file + " " + string.Join(" ", arguments));
        }
        catch (Exception e)
        {
            log("command failed: " + file + ": " + e.Message);
        }
    }

    static void GuardServices(Action<string> log)
    {
        foreach (string unit in GuardUnits)
        {
            Run("/bin/systemctl", log, "mask", "--runtime", unit);
            Run("/bin/systemctl", log, "stop", unit);
        }
        log("service guard applied");
    }

    static void KillLeftovers(Action<string> log)
    {
        Run("/bin/sh", log, "-c",
            "for pid in $(ps -eo pid,comm | awk " +
            "'$2==\"bms-service\" || $2==\"mde-framework\" || $2 ~ /^slive-provider/ " +
            "{print $1}'); do kill -9 \"$pid\" 2>/dev/null; done");
    }

    static void ResetConsent(Action<string> log)
    {
        Run("/usr/bin/vconftool", log, "set", "-t", "int",
            "db/menu/support/softwareupdate/autoupdate", "0", "-f");
        Run("/usr/bin/vconftool", log, "set", "-t", "int",
            "db/menu/support/softwareupdate/preupdate_consent", "0", "-f");
    }

    static bool TryAvocGuard(bool asSdk, string command, Action<string> log)
    {
        try
        {
            var start = new ProcessStartInfo("/usr/bin/systemd-run")
            {
                UseShellExecute = false
            };
            start.ArgumentList.Add("--unit=kurumi-avoc");
            if (asSdk) start.ArgumentList.Add("--uid=901");
            start.ArgumentList.Add("--on-active=20s");
            start.ArgumentList.Add("--collect");
            start.ArgumentList.Add("/bin/sh");
            start.ArgumentList.Add("-c");
            start.ArgumentList.Add(command);
            using var process = Process.Start(start);
            if (process == null) return false;
            if (!process.WaitForExit(10000))
            {
                process.Kill(true);
                log("avoc guard timeout");
                return false;
            }
            if (process.ExitCode != 0)
            {
                log("avoc guard mode " + (asSdk ? "sdk" : "root") +
                    " exit " + process.ExitCode);
                return false;
            }
            log("avoc guard scheduled (" + (asSdk ? "sdk" : "root") + ")");
            return true;
        }
        catch (Exception e)
        {
            log("avoc guard failed: " + e.Message);
            return false;
        }
    }

    static void StartAvocGuard(Action<string> log)
    {
        // O Samsung Home deixa o flag new_home=1; sem ele, Picture Clarity e
        // Picture Mode ficam indisponiveis. O timer de 20s evita a corrida do
        // systemd-run durante o boot. Tenta como sdk; se falhar, root.
        string command =
            "while :; do " +
            "/usr/bin/dbus-send --system " +
            "--dest=org.tizen.tv.avoc /org/tizen/tv/avoc " +
            "org.tizen.tv.avoc.AvOutputControl.SetNewHome int32:0 " +
            ">/dev/null 2>&1; " +
            "/usr/bin/vconftool set -t int " +
            "db/menu/support/softwareupdate/autoupdate 0 -f >/dev/null 2>&1; " +
            "/usr/bin/vconftool set -t int " +
            "db/menu/support/softwareupdate/preupdate_consent 0 -f >/dev/null 2>&1; " +
            "sleep 30; done";
        if (TryAvocGuard(true, command, log)) return;
        TryAvocGuard(false, command, log);
    }

    static void Apply(Action<string> log)
    {
        Require(geteuid() == 0, "must run as root");
        Require(
            new FileInfo("/proc/self/ns/mnt").LinkTarget ==
            new FileInfo("/proc/1/ns/mnt").LinkTarget,
            "wrong mount namespace");
        if (!File.Exists(State + "/enabled"))
        {
            log("disabled");
            return;
        }
        Require(File.Exists(Source), "source ContentList missing");
        Require(Hash(Source) == CustomHash, "source ContentList hash mismatch");
        string current = Hash(Stock);
        if (current == CustomHash && HasOverlay())
        {
            log("already active");
            return;
        }
        Require(current == OriginalHash, "firmware ContentList changed; keeping stock");
        Require(!HasOverlay(), "unknown existing overlay; leaving it untouched");
        bool mounted = false;
        try
        {
            Mount(Source, 4096);              // MS_BIND
            mounted = true;
            Mount(null, 4096 | 32 | 1);       // MS_BIND | MS_REMOUNT | MS_RDONLY
            Require(Hash(Stock) == CustomHash, "mounted ContentList hash mismatch");
            mounted = false;
            log("active: read-only ContentList overlay");
        }
        finally
        {
            if (mounted) umount2(Stock, 0);
        }
    }

    static int Main()
    {
        int diagnosticStatus = 1;
        try
        {
            Require(Hash("/opt/etc/parseinfo.sh") == DiagnosticHash, "original diagnostic changed");
            using var process = Process.Start(new ProcessStartInfo("/opt/etc/parseinfo.sh", "&")
            {
                UseShellExecute = false
            });
            if (!process.WaitForExit(8000))
            {
                process.Kill(true);
                throw new Exception("diagnostic timeout");
            }
            diagnosticStatus = process.ExitCode;
        }
        catch (Exception e)
        {
            Console.Error.WriteLine("KurumiSaver diagnostic: " + e.Message);
        }

        try
        {
            using var logFile = new StreamWriter(State + "/last-boot.log", false) { AutoFlush = true };
            void Log(string text)
            {
                logFile.WriteLine(text);
                Console.WriteLine("KurumiSaver: " + text);
            }
            Log("boot_id=" + File.ReadAllText("/proc/sys/kernel/random/boot_id").Trim());
            Log("diagnostic_exit=" + diagnosticStatus);
            try
            {
                Apply(Log);
            }
            catch (Exception e)
            {
                Log("inactive: " + e.Message);
            }
            GuardServices(Log);
            KillLeftovers(Log);
            ResetConsent(Log);
            StartAvocGuard(Log);
        }
        catch (Exception e)
        {
            Console.Error.WriteLine("KurumiSaver: " + e.Message);
        }

        // O overlay e opcional; uma falha nao pode atrapalhar o boot.
        return diagnosticStatus;
    }
}
