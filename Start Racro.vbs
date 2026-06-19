Set sh = CreateObject("WScript.Shell")
d = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = d
sh.Run "cmd /c """ & d & "\_run_hidden.bat""", 0, False
