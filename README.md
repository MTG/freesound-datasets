# Freesound Datasets

A platform for the collaborative creation of open audio datasets based on Freesound content. Please find more information in our paper:

>  E. Fonseca, J. Pons, X. Favory, F. Font, D. Bogdanov, A. Ferraro, S. Oramas, A. Porter and X. Serra. “Freesound Datasets: A Platform for the Creation of Open Audio Datasets” In *Proceedings of the 18th International Society for Music Information Retrieval Conference*, Suzhou, China, 2017.


## Configuration

Copy `freesound_datasets/local_settings.example.py` to `freesound_datasets/local_settings.py`
and follow the instructions in the file to fill in services credentials for your project.

To allow downloads, you need to fill in

 * `FS_CLIENT_ID`
 * `FS_CLIENT_SECRET`

If you want to log in with an external service fill in the relevant `SOCIAL_AUTH_` keys.

Otherwise, to create a user using Django's models you can run

    docker-compose run --rm web python manage.py createsuperuser

## Running

The first time you load the application you will need to perform migrations:

    docker-compose run --rm web python manage.py migrate

Run Freesound datasets using docker-compose:

    docker-compose up

And point your browser at `http://localhost:8000`.

### Dummy data

You will need test data to develop.
To load some data, first load the dataset fixtures by running

    docker-compose run --rm web python manage.py loaddata datasets/fixtures/initial.json

This will create an empty dataset with a loaded taxonomy.

Once you have the dataset, you can generate fake data (sounds, annotations and votes),
by running

    docker-compose run --rm web python manage.py generate_fake_data fsd 100 5 1000 1000

This will create 100 fake sounds, 5 fake users, 1000 fake annotations and 1000 fake annotation votes.
You can run this command again to generate more data.


