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

```
docker-compose up
```
And point your browser at `http://localhost:8000`.

However, you'll want to have some data in it to test stuff ;)
To load some data, first load dataset fixtures by running

```
docker-compose run web python manage.py loaddata datasets/fixtures/initial.json
```

This will create an empty dataset with a loaded taxonomy.
Once you have the dataset, you can generate fake data (sounds, annotations and votes),
by running

```
docker-compose run web python manage.py generate_fake_data fsd 100 5 1000 1000
```

This will create 100 fake sounds, 5 fake users, 1000 fake annotations and 1000 fake annotation votes.
You can run this command again to generate more data.

 
