param([Parameter(Mandatory)][string]$Name)
# Bring a running app's main window to the front (restore if minimised, maximise for watching).
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
"@
$p = Get-Process $Name -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { "no window for $Name"; exit 1 }
$h = $p.MainWindowHandle
# Windows only lets the foreground process hand over focus; a tap of Alt lifts that lock.
[Win]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [Win]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
[Win]::ShowWindow($h, 3) | Out-Null   # SW_MAXIMIZE
[Win]::BringWindowToTop($h) | Out-Null
[Win]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 300
"{0} in front: {1}" -f $p.ProcessName, ([Win]::GetForegroundWindow() -eq $h)
