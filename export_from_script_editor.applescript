on open droppedItems
	if (count of droppedItems) is 0 then
		display dialog "FCPXMLまたはFCPXML Packageをドロップしてください。"
		return
	end if
	
	set droppedFile to item 1 of droppedItems
	
	-- exporter.py の場所
	set appPath to POSIX path of (path to me)
	set appFolder to do shell script "dirname " & quoted form of appPath
	set exporterPath to appFolder & "/exporter.py"
	
	set inputPath to POSIX path of droppedFile
	
	set commandText to "/usr/bin/env python3 " & quoted form of exporterPath & " " & quoted form of inputPath
	
	try
		set resultText to do shell script commandText
		display dialog resultText buttons {"OK"} default button "OK"
	on error errorMessage number errorNumber
		display dialog "エラー:" & return & errorMessage buttons {"OK"} default button "OK"
	end try
end open