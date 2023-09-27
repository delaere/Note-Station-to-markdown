import pytz
import datetime
import os
import json
import requests
from time import sleep

class Paperless:
    def __init__(self,paperless_url: str = "http://localhost:8000", token: str = None, username: str = None, password: str = None, timeout: float = 5.0):
        self.session = requests.Session() 
        self.paperless_url = paperless_url
        self.timeout = timeout
        self.__set_auth_tokens(token,username,password)
        
    def __set_auth_tokens(self,api_token: str, username: str,password: str):
        response = self.session.get(self.paperless_url, timeout=self.timeout)
        response.raise_for_status()
        csrf_token = response.cookies["csrftoken"]
        if api_token is None:
            response = self.session.post(
                self.paperless_url + "/api/token/",
                json={"username": username, "password":  password},
                headers={"X-CSRFToken": csrf_token},
                timeout=self.timeout,
            )
            response.raise_for_status()
            api_token = response.json()["token"]
        self.session.headers.update({"Authorization": f"Token {api_token}", f"X-CSRFToken": csrf_token})

    def tags(self):
        # return the list of tags
        alltags = {}
        query = self.paperless_url + f"/api/tags/"
        while query is not None:
            tags_info_resp = self.session.get(
                query, timeout=self.timeout,
            )
            tags_info_resp.raise_for_status()
            tags = tags_info_resp.json()
            alltags.update({ t["name"]:t['id'] for t in tags["results"] })
            query = tags["next"]
        return alltags

    def addTag(self,tag, colour: int = None, matching_algorithm: int = 6):
        # add a tag to Paperless
        tagJson = {"name": tag }
        if colour is not None:
            tagJson['colour'] = colour
        if matching_algorithm is not None:
            tagJson['matching_algorithm'] = matching_algorithm
        tag_info_resp = self.session.post(
                self.paperless_url + f"/api/tags/", timeout=self.timeout,
                json = tagJson
                )
        tag_info_resp.raise_for_status()
        tag_info = tag_info_resp.json()
        return { tag_info['name']: tag_info['id'] }

    def findDocument(self,query:str):
        # Query the API for the document info
        info_resp = self.session.get(
            self.paperless_url + f"/api/documents/", timeout=self.timeout,
            params={'query':query}
        )
        info_resp.raise_for_status()
        return info_resp.json()

    def addDocument(self,document: str, fields: dict = None, wait = True):
        # post the document
        # fields can specify: title, created, correspondent, document_type, tags, archive_serial_number
        document = {'document': open(document, 'rb')}
        answer = self.session.post(self.paperless_url + f"/api/documents/post_document/", timeout=self.timeout, files=document, data = fields )
        answer.raise_for_status()
        task_id = answer.json()
        # wait for the completion of the processing task
        if not wait:
            return task_id
        status = "unknown"
        while status!='SUCCESS' and status!='FAILURE':
            # Query the API for the task info
            task_info_resp = self.session.get(
                self.paperless_url + f"/api/tasks/", timeout=self.timeout,
                params={'task_id':task_id}
            )
            if task_info_resp.status_code == 200:
                task_info = task_info_resp.json()
            status = task_info[0]['status']
            sleep(5)
        if status=='FAILURE':
            print(task_info[0]['result'])
        # on completion, return the document id.
        # in case of failure, returns None 
        doc_pk = task_info[0]['related_document']
        return doc_pk

    def addNote(self,doc_pk: int,note: str):
        doc_info_resp = self.session.post(
            self.paperless_url + f"/api/documents/{doc_pk}/notes/", timeout=self.timeout,
            json = {"note": note}
        )
        doc_info_resp.raise_for_status()
        doc_info = doc_info_resp.json()

    def lastASN(self):
        # Query the API for the document info
        # Note: limit doesn't work.
        asn_info_resp = self.session.get(
            self.paperless_url + f"/api/documents/", timeout=self.timeout,
            params={'query':'asn:*', 'ordering':'-archive_serial_number', 'limit':'1'}
        )
        asn_info_resp.raise_for_status()
        asn_info = asn_info_resp.json()
        return asn_info['results'][0]['archive_serial_number']

    def editDocument(self, doc_pk, json):
        # edit the document.
        # example below with *replace* the tags list.
        # json = {"tags": [3] }
        doc_info_resp = sess.patch(
            self.paperless_url + f"/api/documents/{doc_pk}/", timeout=self.timeout,
            json = json
        )
        doc_info_resp.raise_for_status()
        return 

