This script will convert notes from Synology Note Station to plain-text markdown notes and/or copy the attachments to Paperless-ngx.
The script is written in Python and should work on any desktop platform. It's tested on Linux.

After conversion to Markdown, you will get:
1) Directories named like the exported notebooks;
2) Notes in those directories as markdown-syntax plain text files with all in-line images in-place;
3) Assigned tags and links to attachments at the beginning of note text;
4) All images and attached files in `media` sub-directories inside notebook directories.

After the upload to Paperless-ngx, you will get:
1) Documents with the proper title and creation time;
2) Tags in Paperless-ngx corresponding to the Note Station tags;
3) Notes associated to documents, containing a Markdown version of the note containing the attachment.

The main input is the nsx export file produced by Note Station.
Because this export may lack some of the attachments, the code adds the possibility to extract the missing content from 
a manual archive of the Synology directory that contains the raw Note Station data.  
That optional tar.gz backup should be made by connecting as root (by ssh) to the synology server.

# Usage
1) Export your Synology Note Station notebooks by: Setting -> Import and Export -> Export. You will get .nsx file.
2) Adjust the .nsx file permission if required.
3) edit or create your own configuration yaml file (see `config_example.yml`)
4) run the migrate.py script with the appropriate command-line options:
```
./migrate.py --help
usage: migrate.py [-h] [-m] [-p] [-c CONFIG] [-e EXPORT] [-a ARCHIVE] [-d] [-l LIMIT] [-r RESTART]

Script to migrate notes to markdown or to Paperless-ngx

options:
  -h, --help            show this help message and exit
  -m, --md              export to markdown
  -p, --paperless       export to paperless
  -c CONFIG, --config CONFIG
                        config file name (yaml file)
  -e EXPORT, --export EXPORT
                        export file from NoteStation
  -a ARCHIVE, --archive ARCHIVE
                        archived copy of the NoteStation data
  -d, --dry             (Paperless only) dry run: don't copy to Paperless
  -l LIMIT, --limit LIMIT
                        (Paperless only) limit the number of documents to upload
  -r RESTART, --restart RESTART
                        (Paperless only) restart from the given note title

```

# For [QOwnNotes](https://github.com/pbek/QOwnNotes) users
There are several ways to get tags from converted notes to work in QOwnNotes:

## Import tags to QOwnNotes native way
1) Convert .nsx files with default `nsx2md.py` settings;
2) Add notebook directories produced by `nsx2md.py` as QOwnNotes note folders;  
3) Set one of these note folders as current;  
4) Enable provided `import_tags.qml` script in QOwnNotes (Note -> Settings -> Scripting) (`remove_tag_line.py` should be at the same directory);  
5) The script will add 2 new buttons and menu items:  
    `1. Import tags` - to import tags from the tag lines of all the notes in the current note folder  
    `2. Remove tag lines` - to remove the tag lines from all the notes in the current folder  
6) Use the buttons in the according order, any previous QOwnNotes tag data for the note folder will be lost;  
7) Move to the next note folder produced by `nsx2md.py`, repeat #5;  
8) Disable `import_tags.qml` script. That is obligatory.

## "@tag tagging in note text (experimental)" QOwnNotes script
1) For default `@` tag prepends use the following `nsx2md.py` settings:
``` ini
tag_prepend = '@'  # string to prepend each tag in a tag list inside the note, default is empty
tag_delimiter = ' '  # string to delimit tags, default is comma separated list
no_spaces_in_tags = True  # True to replace spaces in tag names with '_', False to keep spaces
```
2) Convert .nsx files;
3) Add notebook directories produced by `migrate.py` as QOwnNotes note folders.
