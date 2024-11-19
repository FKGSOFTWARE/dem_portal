# Define the output file
$outputFile = "code_base.txt"

# Get the tree structure and append it to the output file
"Folder PATH listing:" | Out-File $outputFile
tree /F | Out-File $outputFile -Append

# Define the folder to scan (current directory)
$rootFolder = "C:\Users\fkgde\Desktop\4th Year\_PROJ\dem_portal\dem_web"

# Function to append file content with a header
function Append-FileContent {
    param (
        [string]$filePath
    )

    # Get the filename and append as a label
    $fileName = Get-Item $filePath
    "==== $fileName ====" | Out-File $outputFile -Append

    # Append file content
    Get-Content $filePath | Out-File $outputFile -Append

    # Add a new line for separation between files
    "`n" | Out-File $outputFile -Append
}

# Append content of files in root directory
Append-FileContent "$rootFolder\app.py"
Append-FileContent "$rootFolder\requirements.txt"

# Append content of files in static directory
Append-FileContent "$rootFolder\static\index.html"
Append-FileContent "$rootFolder\static\main.js"
