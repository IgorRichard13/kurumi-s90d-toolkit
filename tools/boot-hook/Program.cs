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
        }
        catch (Exception e)
        {
            Console.Error.WriteLine("KurumiSaver: " + e.Message);
        }

        // O overlay e opcional; uma falha nao pode atrapalhar o boot.
        return diagnosticStatus;
    }
}
