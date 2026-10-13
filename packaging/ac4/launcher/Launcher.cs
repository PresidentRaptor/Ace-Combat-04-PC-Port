// Ace Combat 04 launcher: does what PLAY.bat does, without a console window.
// Rebuild with build-launcher.bat in this folder.
using System;
using System.Collections;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("Ace Combat 04 Launcher")]
[assembly: System.Reflection.AssemblyProduct("Ace Combat 04 Launcher")]

static class Launcher
{
    const string Title = "Ace Combat 04: Shattered Skies";

    [STAThread]
    static int Main(string[] args)
    {
        Application.EnableVisualStyles();

        string root = AppDomain.CurrentDomain.BaseDirectory;
        string runtime = Path.Combine(root, "runtime");
        string exe = Path.Combine(runtime, "ac4.exe");
        string log = Path.Combine(root, "last-play.log");

        if (!File.Exists(exe))
        {
            Error("Could not find runtime\\ac4.exe next to this launcher.\n\nPut the launcher in the game folder (the one containing the 'runtime' folder).");
            return 1;
        }

        string disc = FindDisc(root, args);
        if (disc == null)
        {
            Error("No game disc found.\n\nPut your Ace Combat 04 USA ISO (SLUS-20152) in this folder, or drag the ISO onto the launcher.");
            return 1;
        }

        var psi = new ProcessStartInfo(exe)
        {
            Arguments = "--data " + Quote(runtime) + " --disc " + Quote(disc) + " --vblanks 0 --watchdog 0",
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };

        // Clear any inherited PS2_* variables, then set the ones PLAY.bat sets.
        var keys = new ArrayList(psi.EnvironmentVariables.Keys);
        foreach (string key in keys)
            if (key.StartsWith("PS2_", StringComparison.OrdinalIgnoreCase))
                psi.EnvironmentVariables.Remove(key);
        psi.EnvironmentVariables["PS2_SHADER_DIR"] = Path.Combine(runtime, "shaders");
        psi.EnvironmentVariables["PS2_SAVE_DIR"] = Path.Combine(root, "saves");

        int rc;
        try
        {
            using (var writer = new StreamWriter(log, false, new UTF8Encoding(false)))
            using (var proc = new Process { StartInfo = psi })
            {
                writer.AutoFlush = true;
                object gate = new object();
                DataReceivedEventHandler sink = (s, e) =>
                {
                    if (e.Data != null) lock (gate) writer.WriteLine(e.Data);
                };
                proc.OutputDataReceived += sink;
                proc.ErrorDataReceived += sink;

                proc.Start();
                proc.BeginOutputReadLine();
                proc.BeginErrorReadLine();
                proc.WaitForExit(); // also waits for redirected streams to drain
                rc = proc.ExitCode;
            }
        }
        catch (Exception ex)
        {
            Error("Failed to start the game:\n\n" + ex.Message);
            return 1;
        }

        if (rc != 0)
            Error("Game exited with code " + rc + ".\n\nPlease send last-play.log with your report.");
        return rc;
    }

    static string FindDisc(string root, string[] args)
    {
        if (args.Length > 0 && (File.Exists(args[0]) || Directory.Exists(args[0])))
            return Path.GetFullPath(args[0]);
        string iso = Path.Combine(root, "game.iso");
        if (File.Exists(iso))
            return iso;
        string dir = Path.Combine(root, "game");
        if (File.Exists(Path.Combine(dir, "SYSTEM.CNF")))
            return dir;
        string[] isos = Directory.GetFiles(root, "*.iso");
        if (isos.Length > 0)
        {
            Array.Sort(isos, StringComparer.OrdinalIgnoreCase);
            return isos[0];
        }
        return null;
    }

    // Quote for a Windows command line; a trailing backslash would escape the closing quote.
    static string Quote(string s)
    {
        return "\"" + s.TrimEnd('\\') + "\"";
    }

    static void Error(string msg)
    {
        MessageBox.Show(msg, Title, MessageBoxButtons.OK, MessageBoxIcon.Error);
    }
}
