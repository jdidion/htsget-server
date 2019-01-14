import os
from typing import Optional


class Resource:
    def open(self, mode: str, decompress: Optional[bool] = None):
        pass


class DataStore:
    def lookup(self, name) -> Resource:
        pass


class LocalResource(Resource):
    pass


class LocalDataStore(DataStore):
    def __init__(self, directory=os.getcwd()):
        self.directory = directory

