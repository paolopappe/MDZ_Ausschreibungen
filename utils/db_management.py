import os
import json
from uuid import uuid4
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from utils.prepare_data import prepare_data

STORAGE_PATH = "/ausschreibungen_storage"


class DBManager:

	def __init__(self, db_path, collection_name):
		self._db_path = os.path.join(STORAGE_PATH, db_path)	# for Docker volume
		self._collection_name = collection_name
		# must be enough for a sequence of keywords
		embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
		# init / read
		self.vector_store = Chroma(
			collection_name=collection_name,
			embedding_function=embeddings,
			persist_directory=self._db_path
		)
		# read file index from metadata (if not newly initialized)
		self._file_index_path = os.path.join(self._db_path, f"__{collection_name}_metadata.json")
		self._load_file_index()

	def _load_file_index(self):
		if not os.path.exists(self._file_index_path):
			self._file_index = {}
			return
		else:
			with open(self._file_index_path) as f:
				self._file_index = json.load(f)

	def _save_file_index(self):
		with open(self._file_index_path, "w") as f:
			json.dump(self._file_index, f, indent=4)

	def _chunk2doc(self, chunk: dict) -> Document:
		return Document(
			# page_content=", ".join(chunk["keywords"]) + chunk["summary"],	# keywords as contents
			page_content=chunk["summary"],	# summary as contents
			# page_content=", ".join(chunk["keywords"]),
			metadata={**{"text": chunk["text"]}, **chunk["metadata"]}	# merge text and metadata
		)
	
	def from_dir(self, dir_path):
		pdf_paths = [
			os.path.join(dir_path, filename)
			for filename in os.listdir(dir_path)
			if filename.lower().endswith('.pdf')
		]
		self.add_pdfs(pdf_paths)

	def add_pdf(self, pdf_path, pdf_data=None):
		if pdf_data:
			 chunks = prepare_data( (pdf_path, pdf_data) )
		else:
			chunks = prepare_data(pdf_path)
		docs = [
			self._chunk2doc(chunk)
			for chunk in chunks
		]
		uuids = [str(uuid4()) for _ in range(len(docs))]
		# first we want to delete the document if it exists;
		# since we don't know the changes in the document,
		# we cannot directly use `vector_store.update_document()`
		# because that would require to know strictly which parts
		# changed and which corresponding documents with which ids
		# were associated with those; therefore, we just need to
		# completely rewrite all the entries for this document so
		# here we first need to delete all associated docs
		self.delete_pdf(pdf_path)
		# now add
		self.vector_store.add_documents(docs, ids=uuids)
		# update file index of the instance
		self._file_index[pdf_path] = uuids
		# after everything is added, update the metadata in the DB
		self._save_file_index()

	def delete_pdf(self, pdf_path):
		if pdf_path not in self._file_index: return
		ids_to_delete = self._file_index[pdf_path]
		self.vector_store.delete(ids_to_delete)
		self._file_index.pop(pdf_path)
		# after everything is deleted, update the metadata in the DB
		self._save_file_index()

	def __len__(self):
		return self.vector_store._collection.count()
	

# should be added in Dockerfile
DB_PATH = os.environ["DB_PATH"]
COLLECTION_NAME = os.environ["COLLECTION_NAME"]

_db_manager = DBManager(
    db_path=DB_PATH,
    collection_name=COLLECTION_NAME
)