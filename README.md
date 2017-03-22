# Freesound Datasets

Website to release Freesound-based datasets

Before running this, you'll need to rename `freesound_datasets/local_settings.example.py`
to `freesound_datasets/local_settings.py` and follow the instructions there
to fill in services credentials for your project. The minimum you need is
to fil `FS_CLIENT_ID` and `FS_CLIENT_SECRET` to allow downloads and one
of the authentication mechanisms (we recommend filling `SOCIAL_AUTH_FREESOUND_KEY`
and `SOCIAL_AUTH_FREESOUND_SECRET` so you don't have to create accounts
in pages other than Freesound.

After that, you can easily run Freesound datasets using Docker:
Run `docker-compose up` and point your browser at `http://localhost:8000`.
