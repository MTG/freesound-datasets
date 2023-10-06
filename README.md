# Freesound Annotator
The platform changed its name from *Freesound Datasets* to *Freesound Annotator*.

[Freesound Annotator](https://annotator.freesound.org/) is a platform for the collaborative creation of open audio collections labeled by humans and based on Freesound content. Freesound Annotator allows the following functionalites:
- **explore** the contents of datasets
- **contribute** to the creation of the datasets by providing annotations
- it will allow to **download** different _timestamped_ releases of the datasets
- it also promotes **discussions** around both platform and datasets

This repository serves the following main purposes:
- **development and maintenance** of the Freesound Annotator
- allow people to see the ongoing progress in a **transparent** manner
- concentrate **discussion** from the community

We would like the community to get involved and to **share comments and suggestions** with us and other users. Feel free to take a look at the issues and join ongoing discussions, or create a new issue. We encourage discussion about several aspects of the datasets and the platform, including but not limited to: faulty audio samples, wrong annotations, annotation tasks protocol, etc. You can check the [Discussion page](https://annotator.freesound.org/fsd/discussion/) on the Freesound Annotator for some more ideas for discussion.

The first dataset created through the Freesound Annotator is [FSD](https://annotator.freesound.org/fsd/): a large-scale, general-purpose dataset composed of [Freesound](https://freesound.org/) content annotated with labels from Google’s [AudioSet Ontology](https://research.google.com/audioset/ontology/index.html). All datasets collected through the platform will be openly available under Creative Commons licenses.

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

Run Freesound Annotator using docker-compose:

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


## Add a new dataset with a validation task

1) Create dataset object from the admin

2) Create a taxonomy.json file which looks like the example below and load using command (get the dataset ID from the admin): 

```python manage.py load_taxonomy 'DATASET_ID PATH/TO/TAOXNOMY_FILE.json```

```json
{
    "id1":{
        "id":"id1",
        "name":"Main class",
        "child_ids":["id2"],
        "description":"A description for this cateogry.",
        "citation_uri":"http://en.wikipedia.org/wiki/Artillery",
        "positive_examples_FS":[
            253284,
            85201
        ]
    },
    "id2":{
        "id":"id2",
        "name":"Sub class",
        "parent_ids":["id1"],
        "description":"A description for this cateogry.",
        "positive_examples_FS":[
            1234,
            1235
        ]
    }
}
```

3) Create objects for the taxonomy nodes using command (get the taxonomy ID from the admin):

```python manage.py create_taxonomy_node_instances TAXONOMY_ID```

4) Load candidate sound annotations from a JSON file using the command (`algorithm_name` is ):

```python manage.py load_sounds_for_dataset short_ds_name filepath.json algorithm_name```

```json
{
    "366411":{
      "username":"Rach_Capache",
      "description":"Cat sniffing: sniffing microphone. Recorded with a ZOOM H6 recorder and X/Y capsule. The sound was post-processed to remove any background noise or room tone.",
      "license":"http://creativecommons.org/licenses/by-nc/3.0/",
      "tags":[
         "close",
         "sniffing",
         "cat",
         "kitty",
         "pet",
         "sniff",
         "owi"
      ],
      "previews":"http://www.freesound.org/data/previews/366/366411_5959200-hq.ogg",
      "duration":5.0,
      "category_ids":[
         "id1"
      ],
      "name":"Cat Sniffing.wav"
   },
   "38121":{
      "username":"deprogram",
      "description":"dog bark ",
      "license":"http://creativecommons.org/licenses/by-nc/3.0/",
      "tags":[
         "bark",
         "dog"
      ],
      "previews":"http://www.freesound.org/data/previews/38/38121_389218-hq.ogg",
      "duration":2.9953968254,
      "category_ids":[
         "id2"
      ],
      "name":"bark.wav"
   }
}
```