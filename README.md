# RedditPostDownloader

<p align="center"><img src="https://github.com/ailothaen/RedditArchiver/blob/main/github/logo.png?raw=true" alt="RedditArchiver logo" width="500"></p>

RedditPostDownloader is a modified version of RedditArchiver to downloaded a single reddit post.

For more information on RedditArchiver itself, see [the main repository](https://github.com/ailothaen/RedditArchiver).


## Installing dependencies and setting up tokens

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Edit the file `config.yml` to put all the informations needed to connect (client ID, client secret and refresh token).

If you have no clue about what these options are, follow these steps:
1. [Go here](https://www.reddit.com/prefs/apps) and create an app
2. Use the "script" type, and put `http://localhost:8080` as redirect URI (the other options do not matter)
3. Take note of your client ID and client secret
4. Run the script `authentication.py` to get your refresh token
5. Edit the config file to put the client ID, client secret and refresh token in it.


## Running the script

Run `RUN.bat`, paste the URL of the reddit post you want to download and press enter.
