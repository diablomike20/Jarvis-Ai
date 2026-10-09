$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('C:\Users\ravit\OneDrive\Desktop\Jarvis AI.lnk')
$Shortcut.TargetPath = 'D:\TiTech Prabha Solution\Jarvis AI\Jarvis AI\Jarvis AI-AI---Lite-main\Jarvis AI-AI---Lite-main\.venv\Scripts\pythonw.exe'
$Shortcut.Arguments = '"D:\TiTech Prabha Solution\Jarvis AI\Jarvis AI\Jarvis AI-AI---Lite-main\Jarvis AI-AI---Lite-main\main.py"'
$Shortcut.WorkingDirectory = 'D:\TiTech Prabha Solution\Jarvis AI\Jarvis AI\Jarvis AI-AI---Lite-main\Jarvis AI-AI---Lite-main'
$Shortcut.WindowStyle = 7
$Shortcut.Description = 'Launch Jarvis AI'
if ('D:\TiTech Prabha Solution\Jarvis AI\Jarvis AI\Jarvis AI-AI---Lite-main\Jarvis AI-AI---Lite-main\assets\Brahma_Lite_Logo.ico') { $Shortcut.IconLocation = 'D:\TiTech Prabha Solution\Jarvis AI\Jarvis AI\Jarvis AI-AI---Lite-main\Jarvis AI-AI---Lite-main\assets\Brahma_Lite_Logo.ico,0' }
$Shortcut.Save()