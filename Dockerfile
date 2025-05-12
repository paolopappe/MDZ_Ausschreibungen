FROM python:3.12-slim

# making directory of app
WORKDIR /mdz_ausschreibung_llm 
COPY . .

# pip install packages
RUN pip install -r requirements.txt

# exposing default port for streamlit
EXPOSE 8501

# system variables for the DB
ENV DB_PATH="ausschreibungen_db"
ENV COLLECTION_NAME="prusseit_reiss"

# initialize DB
# RUN python _init_db.py Ausschreibungen

# entrypoint to launch app when container is run
ENTRYPOINT ["python", "-m", "streamlit", "run", "Suche.py"]