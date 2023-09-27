#!/bin/env python
import NoteStation
import argparse

def main():
    # load options
    argParser = argparse.ArgumentParser(
            prog="migrate.py",
            description="Script to migrate notes to markdown or to Paperless-ngx")
    argParser.add_argument("-m", "--md", help="export to markdown", default=False, action='store_true')
    argParser.add_argument("-p", "--paperless", help="export to paperless", default=False, action='store_true')
    argParser.add_argument("-c", "--config", help="config file name (yaml file)")
    argParser.add_argument("-e", "--export", help="export file from NoteStation", default="export.nsx")
    argParser.add_argument("-a", "--archive", help="archived copy of the NoteStation data", default="archive.tgz")
    argParser.add_argument("-d", "--dry", help="(Paperless only) dry run: don't copy to Paperless", default=False, action='store_true')
    argParser.add_argument("-l", "--limit", help="(Paperless only) limit the number of documents to upload", default=None, type=int)
    argParser.add_argument("-r", "--restart", help="(Paperless only) restart from the given note title", default=None)
    args = argParser.parse_args()

    nsexport = NoteStation.NoteStationExport(args.export,args.archive)
    if args.md:
        print("Exporting to Markdown")
        nsexport.toMarkdown(args.config)
    if args.paperless:
        print("Exporting to Paperless")
        nsexport.toPaperless(args.config,dryRun=args.dry,limit=args.limit, restartFrom=args.restart)

if __name__ == "__main__":
    main()

