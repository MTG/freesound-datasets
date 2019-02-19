# Freesound Datasets

The [Freesound Datasets platform](https://datasets.freesound.org/) is a platform for the collaborative creation of open audio collections labeled by humans and based on Freesound content. The Freesound Datasets platform allows the following functionalites:
- **explore** the contents of datasets
- **contribute** to the creation of the datasets by providing annotations
- it will allow to **download** different _timestamped_ releases of the datasets
- it also promotes **discussions** around both platform and datasets

This repository serves the following main purposes:
- **development and maintenance** of the Freesound Datasets platform
- allow people to see the ongoing progress in a **transparent** manner
- concentrate **discussion** from the community

We would like the community to get involved and to **share comments and suggestions** with us and other users. Feel free to take a look at the issues and join ongoing discussions, or create a new issue. We encourage discussion about several aspects of the datasets and the platform, including but not limited to: faulty audio samples, wrong annotations, annotation tasks protocol, etc. You can check the [Discussion page](https://datasets.freesound.org/fsd/discussion/) on the Freesound Datasets platform for some more ideas for discussion.

The first dataset created through the Freesound Datasets platform is [FSD](https://datasets.freesound.org/fsd/): a large-scale, general-purpose dataset composed of [Freesound](https://freesound.org/) content annotated with labels from Google’s [AudioSet Ontology](https://research.google.com/audioset/ontology/index.html). All datasets collected through the platform will be openly available under Creative Commons licenses.

You can find more information about the platform and the creation of FSD in our paper:

>  E. Fonseca, J. Pons, X. Favory, F. Font, D. Bogdanov, A. Ferraro, S. Oramas, A. Porter and X. Serra. “Freesound Datasets: A Platform for the Creation of Open Audio Datasets” In *Proceedings of the 18th International Society for Music Information Retrieval Conference*, Suzhou, China, 2017.
 


## Getting Started

You'll need to have [`docker`](https://docs.docker.com/install/) and [`docker-compose`](https://docs.docker.com/compose/install/) installed.

### Configuration

Copy `freesound_datasets/local_settings.example.py` to `freesound_datasets/local_settings.py`
and follow the instructions in the file to fill in services credentials for your project.

To allow downloads, you need to fill in

 * `FS_CLIENT_ID`
 * `FS_CLIENT_SECRET`

If you want to log in with an external service fill in the relevant `SOCIAL_AUTH_` keys.

Otherwise, to create a user using Django's models you can run

    docker-compose run --rm web python manage.py createsuperuser

You will need to install the PostgreSQL [`pg_trgm`](https://www.postgresql.org/docs/9.6/pgtrgm.html) extension in order to enable the text-search in the *sound curation task*. After having started the containers (`docker-compose up`), from an other terminal, you can run

    docker-compose run --rm db psql -h db -U postgres
    CREATE EXTENSION pg_trgm;


### Running

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


