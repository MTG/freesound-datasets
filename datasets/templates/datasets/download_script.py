import urllib2
import json
import sys
import cgi
import os
import time

dataset_url = '{{dataset_url}}'
get_code_url = 'https://freesound.org/apiv2/oauth2/authorize/?response_type=code&client_id={{get_code_url}}'
get_access_token_url = '{{access_token_url}}?'

verbose = False
tmp_path = "/tmp"
download_path = "fs_dataset"
progress = {"downloaded": [], "access_token": None}

sys.stdout.write("FreesoundDataset download script\n")
sys.stdout.write("--------------------------------\n")
if len(sys.argv) > 1 and sys.argv[1] == '-v':
    verbose = True

if verbose:
    sys.stdout.write("please, enter the location to place the downlaoded files: (default: ./fs_dataset)\n")
    download_path = raw_input() or 'fs_dataset'

if not os.path.exists(download_path):
    os.makedirs(download_path+tmp_path)

if os.path.exists(download_path+"/progress.json"):
    progress = json.load(open(download_path+"/progress.json"))

if not 'features' in progress:
    sys.stdout.write("You have the option to download the dataset with the "\
            + "sounds together with the audio features and/or the metadata."\
            + "Please, Choose an option:\n"\
            + "1) Download sound+features+metadata (default)\n"\
            + "2) Download sound+features\n3) Download sound+metadata\n")
    progress['features'] = raw_input() or '1'

# First try to get access_token from progress.json, if it's expired try to refresh
expired = True
if progress["access_token"]:
    expired = int(time.time())+5*60 > progress["curr_time"] + progress["access_token"]["expires_in"]
    if expired:
        progress["access_token"]["refresh_token"]
        try:
            refresh_url = get_access_token_url+"refresh_token="+progress["access_token"]["refresh_token"]
            rsp = urllib2.urlopen(refresh_url)
            access_token = json.load(rsp)
            progress["access_token"] = access_token
            progress["curr_time"] = int(time.time())

            if verbose:
                sys.stdout.write("Refreshed access_token successfully  %s\n" % access_token["access_token"])

            expired = False
        except urllib2.HTTPError:
                sys.stdout.write("Failed refreshing access_token, moving on...\n")

# If access_token it's expired then get a new one using the code given by the user
while expired:
    sys.stdout.write("please, go to:\n")
    sys.stdout.write(get_code_url)
    sys.stdout.write("\nand copy the code here:\n")
    code = raw_input()

    if verbose:
        sys.stdout.write("Requesting access_token using code: %s\n" % code)

    try:
        rsp = urllib2.urlopen(get_access_token_url+"code="+code)
        access_token = json.load(rsp)
        progress["access_token"] = access_token
        progress["curr_time"] = int(time.time())

        if verbose:
            sys.stdout.write("Got access_token successfully  %s\n" % access_token["access_token"])

        # Make to call to get list of all the sound ids to download
        rsp = urllib2.urlopen(dataset_url)
        progress["sound_ids"] = json.load(rsp)['sounds']

        expired = False
    except urllib2.HTTPError:
            sys.stdout.write("Failed getting access_token, retrying...\n")

sounds_dict = {sid: 'https://freesound.org/apiv2/sounds/%s/' % sid for sid in progress['sound_ids']}

# Now start download of sounds on sounds_dict
sys.stdout.write("Starting download of %d sounds\n" % len(sounds_dict.keys()))

token = progress["access_token"]["access_token"]
headers = {'Authorization': 'Bearer %s' % token}
for i in sounds_dict.keys():
    if i in progress["downloaded"]:
        sys.stdout.write("Sound %s already downloaded, skipping\n" % i)
        continue
    response = 'y'
    if verbose:
        sys.stdout.write("Downloading sound: %s\n" % sounds_dict[i])
        sys.stdout.write("Do you want to download this sound? (enter: yes(y) to download or no(n) to skip)\n")
        response = raw_input()
    if response in ('y', 'yes'):
        sys.stdout.write("Downloading... [%d/%d]" % (len(progress["downloaded"])+1, len(sounds_dict.keys())))

        try:
            req = urllib2.Request(sounds_dict[i]+"download/", headers=headers)
            with open(str(i), 'wb') as output:
                res = urllib2.urlopen(req)
                output.write(res.read())
            f_name = download_path + tmp_path + '/' + cgi.parse_header(res.headers['content-disposition'])[1]['filename']

            os.rename(str(i), f_name)

            if progress["features"] in ['1', '3']:
                req = urllib2.Request(sounds_dict[i], headers=headers)
                with open(os.path.splitext(f_name)[0]+'.json', 'wb') as output:
                    output.write(urllib2.urlopen(req).read())

            if progress["features"] in ['1', '2']:
                req = urllib2.Request(sounds_dict[i]+"analysis/", headers=headers)
                with open(os.path.splitext(f_name)[0]+'-analysis.json', 'wb') as output:
                    output.write(urllib2.urlopen(req).read())

        except urllib2.HTTPError:
            sys.stdout.write("Failed to download %s, skipping\n" % sounds_dict[i])
            continue
    progress["downloaded"].append(i)
    sys.stdout.write(("\rDone: %d/%d                                              "\
            +"\n") % (len(progress["downloaded"]), len(sounds_dict.keys())))
    sys.stdout.flush()

    with open(download_path+"/progress.json", 'w') as outfile:
        json.dump(progress, outfile)

for i in os.listdir(download_path + tmp_path):
    f_name_from = download_path + tmp_path + '/' + i
    f_name_to = download_path + '/' + i
    os.rename(f_name_from,f_name_to)

os.rmdir(download_path + tmp_path)

sys.stdout.write("Download finished!\n")
