rm -rf build
rm -rf dist
pyinstaller.exe --paths=./M3K4 M3K4/main.py -n M3K4 -y -F
