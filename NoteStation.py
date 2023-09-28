import re
import os
import tarfile
import zipfile
import pandoc
import json
import yaml
import time
import pytz
import tempfile
import signal
import urllib.request
from pathlib import Path
from datetime import datetime
from urllib.parse import unquote
import Paperless
import requests

abort = False

def handler(signum, frame):
    print("Terminating...")
    global abort 
    abort = True

def sanitise_path_string(path_str):
    for char in (':', '/', '\\', '|'):
        path_str = path_str.replace(char, '-')
    for char in ('?', '*'):
        path_str = path_str.replace(char, '')
    path_str = path_str.replace('<', '(')       
    path_str = path_str.replace('>', ')')
    path_str = path_str.replace('"', "'")
    path_str = urllib.parse.unquote(path_str)
            
    return path_str[:100]

def newdir(basepath, name):
    thepath = Path(basepath) / sanitise_path_string(name)
    n = 1
    while thepath.is_dir():
        thepath =  Path(basepath) / Path('{}_{}'.format(sanitise_path_string(name), n))
        n += 1
    return thepath

def newfile(basepath, filename):
    name = filename
    n = 1
    while (Path(basepath) / name).is_file():
        name_parts = name.rpartition('.')
        name = ''.join((name_parts[0], '_{}'.format(n), name_parts[1], name_parts[2]))
        n += 1
    return name

def link(path,name,absolute=False,as_URI=True):
    if as_URI:
        if absolute:
            link_path = (Path(path) / name).as_uri()
        else:
            link_path = 'file://{}/{}'.format("media",urllib.request.pathname2url(name))
    else:
        if absolute:
            link_path = str(Path(path) / name)
        else:
            link_path = f'media/{name}'
    return link_path

# each note is in a notebook.
class Notebook:
    def __init__(self,jsondesc):
        self.title = jsondesc['title'] or 'Untitled'
        self.name = self.title
        self.ctime = jsondesc.get('ctime','')
        self.mtime = jsondesc.get('mtime','')
        self.notes = []
        self.path = None

    def addNote(self,note):
        self.notes.append(note)
        note.notebook = self

    def setPath(self,path):
        self.path = path

# each note is a file with a json representation.
# here we only decode the mostly relevant fields.
class Note:
    def __init__(self,jsondesc):
        # main fields
        self.title = jsondesc['title']
        self.ctime = jsondesc.get('ctime', '')
        self.mtime = jsondesc.get('mtime', '')
        # link with the parent notebook
        self.notebook_id = jsondesc['parent_id']
        self.notebook = None
        # tags
        self.tags = jsondesc.get('tag',[])
        # content (note text)
        self.content = re.sub('<img class=[^>]*syno-notestation-image-object[^>]*src=[^>]*ref=',
                              '<img src=', jsondesc.get('content', ''))
        doc = pandoc.read(self.content, format="html")
        self.content = pandoc.write(doc, format='markdown_strict+pipe_tables-raw_html')
        # attachments
        attachments_data = jsondesc.get('attachment',{})
        attachments_data = {} if attachments_data is None else attachments_data
        self.attachment_list = []
        for attachment in attachments_data.values():
            # read the various fields attached to an attachment.
            ref = attachment.get('ref', '')
            md5 = attachment['md5']
            source = attachment.get('source', '')
            name = sanitise_path_string(attachment['name'])
            name = name.replace('ns_attach_image_', '')
            self.attachment_list.append({'name':name, 'md5':md5, 'ref':ref, 'source':source})

class NoteStationExport:
    def __init__(self, exportfile: str, archive = None):
        # open export
        self.filename = exportfile
        self.nsx_file = zipfile.ZipFile(self.filename)
        # load config data: dict_keys(['note', 'notebook', 'shortcut'])
        self.config_data = json.loads(self.nsx_file.read('config.json').decode('utf-8'))
        # notebooks
        self.notebooks = {}
        self.notebooks['1027_#00000000'] = Notebook({'title':'Recycle bin'})
        for notebook_id in self.config_data['notebook']:
            notebook_data = json.loads(self.nsx_file.read(notebook_id).decode('utf-8'))
            self.notebooks[notebook_id] = Notebook(notebook_data)
        # notes
        self.notes = {}
        for note_id in self.config_data['note']:
            note_data = json.loads(self.nsx_file.read(note_id).decode('utf-8'))
            self.notes[note_id] = Note(note_data)
            self.notebooks[self.notes[note_id].notebook_id].addNote(self.notes[note_id])
        # open the tar file and get all entries related to the note
        # if provided, open the archive with full NoteStation content (extracted by hand from the server)
        if archive: 
            self.notestation = tarfile.open(archive, "r:gz")
            #self.rawnotes = self.notestation.getmembers()
        else:
            self.notestation = []

    def saveAttachmentFromArchive(self,note_id,md5,path="./",filename=None):
        thenote = [ member for member in self.notestation if note_id in member.name ]
        # if no filename is provided, look for it in the note data
        if filename is None:
            for file in thenote:
                if not file.isfile():
                    continue
                if "version/text" in file.name:
                    try:
                        attachmentdata = json.load(self.notestation.extractfile(file))
                        for i in attachmentdata.values():
                            attachmentName = i['name']
                            attachmentMd5  = i['md5']
                            if attachmentMd5 == md5:
                                filename = attachmentName
                                break
                    except:
                        # normal to get exceptions here
                        # not all version/text/ are json, and not all json have name and md5.
                        pass
        if filename is None:
            raise KeyError(f"{md5} filename not found in archive.")
        # get the attachment data
        for file in thenote:
            if not file.isfile():
                continue
            if "metabinary_info" in file.name:
                attachmentdata = json.load(self.notestation.extractfile(file))
                attachmentmd5 = attachmentdata['name']
                if attachmentmd5 == md5:
                    # found the right attachment. Save it.
                    with open(Path(Path(path) / filename),"wb") as output:
                        output.write(self.notestation.extractfile(f"NoteStation/{note_id}/metabinary/{os.path.basename(file.name)}").read())
                    return
        # if we get here, the attachment was not found.
        raise KeyError(f"{filename} not found in archive.")

    @staticmethod
    def __create_yaml_meta_block(cfg,note,attachment_list):
        # load config
        insert_title = cfg['insert_title']
        insert_ctime = cfg['insert_ctime']
        insert_mtime = cfg['insert_mtime']
        tags = cfg['tags']
        tag_prepend = cfg['tag_prepend']
        tag_delimiter = cfg['tag_delimiter']
        no_spaces_in_tags = cfg['no_spaces_in_tags']
        # create the block
        yaml_block = '---\n'
        if insert_title:
            yaml_block = '{}Title: "{}"\n'.format(yaml_block, note.title)
        if insert_ctime and note.ctime:
            yaml_text_ctime = time.strftime('%Y-%m-%d %H:%M', time.localtime(note.ctime))
            yaml_block = '{}Created: "{}"\n'.format(yaml_block, yaml_text_ctime)
        if insert_mtime and note.mtime:
            yaml_text_mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(note.mtime))
            yaml_block = '{}Modified: "{}"\n'.format(yaml_block, yaml_text_mtime)
        if tags and len(note.tags):
            note_tags = [tag.replace(' ', '_') for tag in note.tags] if no_spaces_in_tags else note.tags
            yaml_tag_list = tag_delimiter.join(''.join((tag_prepend, tag)) for tag in note_tags)
            yaml_block = '{}Tags: [{}]\n'.format(yaml_block, yaml_tag_list)
        yaml_block = '{}---\n'.format(yaml_block)
        if attachment_list:
            yaml_block = '{}\nAttachments:  {}\n'.format(yaml_block, ', '.join(attachment_list))
        return yaml_block

    @staticmethod
    def __create_text_meta_block(cfg,note,attachment_list):
        # load config
        insert_title = cfg['insert_title']
        insert_ctime = cfg['insert_ctime']
        insert_mtime = cfg['insert_mtime']
        tags = cfg['tags']
        tag_prepend = cfg['tag_prepend']
        tag_delimiter = cfg['tag_delimiter']
        no_spaces_in_tags = cfg['no_spaces_in_tags']
        # create the block
        text_block = ''
        if insert_mtime and note.mtime:
            text_mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(note.mtime))
            text_block = 'Modified: {}  \n{}'.format(text_mtime, text_block)
        if insert_ctime and note.ctime:
            text_ctime = time.strftime('%Y-%m-%d %H:%M', time.localtime(note.ctime))
            text_block = 'Created: {}  \n{}'.format(text_ctime, text_block)
        if attachment_list:
            text_block = 'Attachments: {}  \n{}'.format(', '.join(attachment_list), text_block)
        if tags and len(note.tags):
            note_tags = [tag.replace(' ', '_') for tag in note.tags] if no_spaces_in_tags else note.tags
            text_tag_list = tag_delimiter.join(''.join((tag_prepend, tag)) for tag in note_tags)
            text_block = 'Tags: {}  \n{}'.format(text_tag_list, text_block)
        if insert_title:
            text_block = '{}\n{}\n{}'.format(note.title, '=' * len(note.title), text_block)
        return text_block

    def toMarkdown(self, configfile):
        # load the config
        with open(configfile, 'r') as ymlfile:
            cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
        basepath = cfg['basepath']
        # first create the tree
        for notebook in self.notebooks.values():
            notebook_path = newdir(os.path.abspath(basepath),notebook.name)
            notebook_media_path = Path(notebook_path / "media")
            notebook_media_path.mkdir(parents=True)
            notebook.setPath((notebook_path,notebook_media_path))
        # then loop on notes and save to disk
        for note_id,note in self.notes.items():
            content = note.content
            title = note.title
            notebook = note.notebook
            attachment_list = []
            for attachment in note.attachment_list:
                # path the to the attachment...
                filename = newfile(notebook.path[1],attachment['name'])
                link_path = link(notebook.path[1],filename,cfg["absolute_links"],cfg["links_as_URI"])
                # save the attachment with the proper name.
                if 'file_' + attachment['md5'] in self.nsx_file.namelist():
                    (Path(notebook.path[1]) / filename).write_bytes(self.nsx_file.read('file_' + attachment['md5']))
                    attachment_link = '[{}]({})'.format(attachment['name'], link_path)
                else:
                    try:
                        self.saveAttachmentFromArchive(note_id,attachment['md5'],path=notebook.path[1],filename=filename)
                        attachment_link = '[{}]({})'.format(attachment['name'], link_path)
                    except KeyError:
                        if attachment['source']:
                            attachment_link = '[{}]({})'.format(attachment['name'], attachment['source'])
                        else:
                            print('Can\'t find attachment "{}" of note "{}"'.format(attachment['name'], note_title))
                            attachment_link = '[NOT FOUND]({})'.format(link_path)
                # ref and source
                if attachment['ref'] and attachment['source']:
                    content = content.replace(attachment['ref'], attachment['source'])
                elif attachment['ref']:
                    content = content.replace(attachment['ref'], link_path)
                else:
                    attachment_list.append(attachment_link)
            # add tags and other data to the content.
            if len(note.tags) or len(attachment_list) or cfg['insert_title'] or cfg['insert_ctime'] or cfg['insert_mtime']:
                content = '\n' + content
            content = f'{self.__create_yaml_meta_block(cfg,note,attachment_list) if cfg["meta_data_in_yaml"] else self.__create_text_meta_block(cfg,note,attachment_list)}\n{content}'
            if cfg['creation_date_in_filename'] and note.ctime:
                note_title = time.strftime('%Y-%m-%d ', time.localtime(note.ctime)) + note.title
            else:
                note_title = note.title
            # write md file
            md_file_path = Path(notebook.path[0])/newfile(notebook.path[0],f'{sanitise_path_string(note_title)}.md')
            md_file_path.write_text(content, 'utf-8')
        # delete useless media directories and Recycle bin
        for notebook in self.notebooks.values():
            try:
                notebook.path[1].rmdir()
            except OSError:
                pass
        try:
            self.notebooks['1027_#00000000'].path[0].rmdir()
        except OSError:
            pass
        return

    def toPaperless(self, configfile, dryRun = False, limit: int = None, restartFrom = None):
        original_sigint_handler = signal.getsignal(signal.SIGINT)
        # we setup a signal handler that will finish the import of the current file before gracefully ending.
        signal.signal(signal.SIGINT, handler)
        # load the config
        with open(configfile, 'r') as ymlfile:
            cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
        paperless_url = cfg['paperless_url']
        username = cfg.get('username',None)
        password = cfg.get('password',None)
        token = cfg.get('token',None)
        timeout = cfg.get('timeout',5.0)
        extensions_all = set(cfg['extensions'])
        htmlnote_ignore = set(cfg['htmlnote_ignore'])
        timezone = cfg['timezone']
        if dryRun:
            print("Dry run. Nothing will be sent to Paperless")
        # initialize the paperless client
        paperless = Paperless.Paperless(paperless_url=paperless_url, username=username, password=password, token=token, timeout=timeout)
        # get the list of existing tags
        knownTags = paperless.tags()
        # create a tmp directory where to store attachments before upload
        ignored = []
        uploadCount = 0
        with tempfile.TemporaryDirectory() as tmpdirname:
            # loop over the notes
            for note_id,note in self.notes.items():
                content = note.content
                title = note.title
                notebook = note.notebook
                ctime = note.ctime
                mtime = note.mtime 
                tags = list(set([ t.lower() for t in note.tags]+[notebook.name.lower()]))
                htmlnote = any([ "htm" in e for _,e in [ os.path.splitext(file) for file in [ attachment['name'] for attachment in note.attachment_list ] ]])
                extensions = extensions_all if not htmlnote else extensions_all.difference(htmlnote_ignore)
                # skip all notes until... 
                if restartFrom is not None:
                    if title != restartFrom:
                        continue
                    else:
                        restartFrom = None
                for attachment in note.attachment_list:
                    # ignore attachments that are not in this list.
                    _, file_extension = os.path.splitext(attachment['name'])
                    if file_extension.lower() not in extensions:
                        print(f"ignoring attachment {attachment['name']} in note {title}")
                        ignored.append((title,attachment['name'],"Wrong extension"))
                        continue
                    # check for existing entry
                    search = paperless.findDocument(query=f"title:'{title}'")
                    found = False
                    for entry in search["results"]:
                        if entry["original_file_name"]==attachment['name']:
                            found = True
                            break
                    # if we found the same filename with the same title, skip
                    if found:
                        print(f"ignoring duplicated {title} ({attachment['name']})")
                        ignored.append((title,attachment['name'],"DUPLICATE"))
                        continue 
                    print(f"uploading {attachment['name']} as {title}")
                    if dryRun:
                        uploadCount += 1
                        if abort or (limit is not None and uploadCount>=limit):
                            break
                        continue
                    # extract the attachment
                    if 'file_' + attachment['md5'] in self.nsx_file.namelist():
                        (Path(tmpdirname) / attachment['name']).write_bytes(self.nsx_file.read('file_' + attachment['md5']))
                    else:
                        try:
                            self.saveAttachmentFromArchive(note_id,attachment['md5'],path=tmpdirname,filename=attachment['name'])
                        except KeyError:
                            pass
                    try:
                        # check that tags exist, add them otherwise
                        for tag in tags:
                            if tag not in knownTags.keys():
                                knownTags.update(paperless.addTag(tag, matching_algorithm = 0))
                        # post the document and wait for the task to be over
                        fields = {'title': title, 'tags':[ knownTags[tag] for tag in tags ], 'created': datetime.fromtimestamp(ctime, pytz.timezone(timezone)).isoformat()}
                        doc_pk = paperless.addDocument(Path(tmpdirname) / attachment['name'], fields=fields, wait = True)
                        # delete the tmp file
                        (Path(tmpdirname) / attachment['name']).unlink()
                        # set the content as note
                        if doc_pk is not None:
                            # count as successful
                            uploadCount += 1
                            paperless.addNote(int(doc_pk), note=content)
                        else:
                            ignored.append((title,attachment['name'],"Failed upload"))
                    except requests.exceptions.RequestException: 
                        ignored.append((title,attachment['name'],"Exception"))
                    if abort or (limit is not None and uploadCount>=limit):
                        break
                if abort or (limit is not None and uploadCount>=limit):
                    break
            # report
            print(f"Uploaded {uploadCount} documents.")
            if len(ignored):
                print(f"The following {len(ignored)} documents were not uploaded:")
                for note,doc,reason in ignored:
                    print(f"{reason}: Note {note}: Document {doc}.")
            print("Done")
            signal.signal(signal.SIGINT, original_sigint_handler)

