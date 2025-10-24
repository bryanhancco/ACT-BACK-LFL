# loaders.py
from langchain_core.documents import Document
from langchain_community.document_loaders.parsers.pdf import PyPDFParser
from langchain_core.document_loaders.blob_loaders import Blob
from typing import List, Optional, Union
from langchain_core.document_loaders.base import BaseLoader

class CustomPDFLoader(BaseLoader):
    def __init__(self, filepath: str, password: Optional[Union[str, bytes]] = None,
                 extract_images: bool = False):
        # Initialize with a file path, optional password, and an image extraction flag
        self.filepath = filepath
        self.filename = filepath.split('/')[-1]  # Get just the filename
        self.parser = PyPDFParser(password=password, extract_images=extract_images)

    def load(self) -> List[Document]:
        # Read the file from disk as binary
        with open(self.filepath, 'rb') as f:
            file_data = f.read()

        # Convert the binary data into a Blob object required by the parser
        blob = Blob.from_data(file_data)
        documents = list(self.parser.parse(blob))

        # Add the filename as metadata to each document for identification
        for doc in documents:
            doc.metadata.update({'source': self.filename})

        return documents

class CustomTextLoader:
    def __init__(self, file_path):
        self.file_path = file_path

    def load_and_split(self, text_splitter):
        with open(self.file_path, "r", encoding="utf-8") as f:
            text = f.read()
        docs = text_splitter.split_documents([Document(page_content=text, metadata={"source": self.file_path})])
        return docs
