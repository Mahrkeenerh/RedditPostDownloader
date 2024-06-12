# 3rd party modules
from anytree import Node, PreOrderIter
import praw, prawcore, markdown2, yaml, colored

# stdlib
import datetime, os, sys, re

__NAME__ = "RedditPostDownloader"
__VERSION__ = "2.1.0"

# -------------------------- #
# Functions                  #
# -------------------------- #

def extract_id(url):
    """
    Extracts the submission ID from a supplied URL
    """
    regexes = (r"^([a-z0-9]+)/?$",
    r"^https?:\/\/(?:old|new|www)?\.reddit\.com\/([a-z0-9]+)\/?$",
    r"^https?:\/\/(?:old|new|www)?\.reddit\.com\/r\/[a-zA-Z0-9\-_]+\/comments\/([a-z0-9]+)\/?")

    for regex in regexes:
        result = re.search(regex, url)
        if result is not None:
            return result.group(1)


def connect():
    """
    Initiates and tests the connection to Reddit.
    """
    reddit = praw.Reddit(client_id=config['reddit']['client-id'], client_secret=config['reddit']['client-secret'], refresh_token=config['reddit']['refresh-token'], user_agent=f"{__NAME__} v{__VERSION__} by /u/ailothaen")
    reddit.auth.scopes()
    return reddit


def get_saved_submissions(extended=False, limit=1000):
    """
    Retrieves the list of saved submissions IDs of the authenticated user.
    If extended is True: returns as well the submissions which the user saved a comment from
    """
    submission_ids = []
    for item in reddit.user.me().saved(limit=limit):
        if item.name[0:2] == "t3":
            submission_ids.append(item.id)
        elif item.name[0:2] == "t1" and extended:
            submission_ids.append(item.link_id[3:])

    return submission_ids


def get_upvoted_submissions(limit=1000):
    """
    Retrieves the list of upvoted submissions IDs of the authenticated user.
    """
    submission_ids = []
    for item in reddit.user.me().upvoted(limit=limit):
        # Reddit seemingly does not give upvoted comments
        if item.name[0:2] == "t3":
            submission_ids.append(item.id)
    
    return submission_ids


def get_posted_submissions(author=None, extended=False, limit=1000):
    """
    Retrieves the list of submissions IDs posted by the authenticated user.
    If extended is True: returns as well the submissions which the user posted a comment into
    """
    submission_ids = []
    if author is None:
        user = reddit.user.me()
    else:
        user = reddit.redditor(author)
    
    if extended:
        for item in user.submissions.new(limit=limit*2):
            submission_ids.append([item.id, item.created_utc])
        for item in user.comments.new(limit=limit*2):
            submission_ids.append([item.submission.id, item.created_utc])

        # keeping only the <limit> newest comments/submissions
        submission_ids.sort(key=lambda x: x[1], reverse=True)
        submission_ids = [item[0] for item in submission_ids[:10]]
    else:
        for item in user.submissions.new(limit=limit):
            submission_ids.append(item.id)
    
    return submission_ids


def comment_parser(initial_text):
    """
    Parses Reddit's pseudo-markdown into HTML formatting
    """
    # removing HTML characters
    text = initial_text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')

    # transforming markdown to HTML
    text = markdown2.markdown(text)

    # converting linebreaks to HTML
    text = text.replace('\n\n', '</p><p>')
    text = text.replace('\n', '<br>')
    
    # removing the last <br> that is here for a weird reason
    if text[-4:] == '<br>':
        text = text[:-4]

    return text


def get_submission(reddit, submission_id):
    """
    Retrieves submission object 
    """
    submission = reddit.submission(id=submission_id)
    nb_replies = submission.num_comments
    return submission, nb_replies


def download_submission(submission, submission_id):
    """
    Retrieves the submission and its comments from Reddit API.
    Returns two lists, one being a flat list of comments with their attributes (comments_forest), the other one being the tree structure of the submission (comments_index)
    """
    # Contains all the node objects (for the tree structure)
    comments_index = {}
    # Contains all the comment objects
    comments_forest = {}

    # Creating root node: the submission itself
    comments_index['t3_'+submission_id] = Node('t3_'+submission_id)

    # Getting all comments in tree order, according to the sorting algorithm defined.
    # See https://praw.readthedocs.io/en/latest/tutorials/comments.html#extracting-comments
    submission.comments.replace_more(limit=None)

    # Filling index and forest
    comment_queue = submission.comments[:] 
    while comment_queue:
        comment = comment_queue.pop(0)
        comments_index['t1_'+comment.id] = Node('t1_'+comment.id, parent=comments_index[comment.parent_id])
        comments_forest['t1_'+comment.id] = {'a': '(deleted)' if comment.author is None else comment.author.name, 'b': '(deleted)' if comment.body is None else comment.body, 'd': comment.distinguished, 'e': comment.edited, 'l': comment.permalink ,'o': comment.is_submitter, 's': comment.score, 't': comment.created_utc}
        comment_queue.extend(comment.replies)

    return submission, comments_index, comments_forest


def generate_html(submission, submission_id, now_str, sort, comments_index, comments_forest):
    """
    Generates HTML structure with the submission, its replies and all its info in it.
    Note: As now, "sort" is unused. Todo?
    """
    # Beginning of file, with <head> section
    html_head = f"""<!doctype html><html><head><meta charset="utf-8"/><title>{submission.subreddit.display_name} – {submission.title}</title></head><body>"""

    # Header of file, with submission info
    html_submission = f"""<h1><a href="{config['reddit']['root']}/r/{submission.subreddit.display_name}/">/r/{submission.subreddit.display_name}</a> – <a href="{config['reddit']['root']}{submission.permalink}">{submission.title}</a></h1><h2>Snapshot taken on {now_str}<br/>Posts: {submission.num_comments} – Score: {submission.score} ({int(submission.upvote_ratio*100)}% upvoted) – Flair: {'None' if submission.link_flair_text is None else submission.link_flair_text} – Sorted by: {sort}<br/>Sticky: {'No' if submission.stickied is False else 'Yes'} – Spoiler: {'No' if submission.spoiler is False else 'Yes'} – NSFW: {'No' if submission.over_18 is False else 'Yes'} – OC: {'No' if submission.is_original_content is False else 'Yes'} – Locked: {'No' if submission.locked is False else 'Yes'}</h2><p><em>Snapshot taken from {__NAME__} v{__VERSION__}. All times are UTC.</em></p>"""

    # First comment (which is actually OP's post)
    html_firstpost = f"""<h3>Original post</h3><div class="b p f l1" id="t3_{submission_id}"><header><a href="{config['reddit']['root']}/u/{'(deleted)' if submission.author is None else submission.author.name}">{'(deleted)' if submission.author is None else submission.author.name}</a>, on {datetime.datetime.fromtimestamp(submission.created_utc).strftime(config["defaults"]["dateformat"])}</header>{comment_parser(submission.selftext)}</div><h3>Comments</h3>"""

    # Iterating through the tree to put comments in right order

    html_comments = ''
    previous_comment_level = 1 # We begin at level 1.
    comment_counter = 1 # Comment counter

    #for comment in generator:
    for node in PreOrderIter(comments_index['t3_'+submission_id]):
        current_comment_level = node.depth
        current_comment_id = node.name

        if node.name[:2] == 't3': # root is the submission itself, we ignore it
            continue

        # We close as much comments as we need to.
        # Is this is a sibling (= same level), we just close one comment.
        # If this is on another branch, we close as much comments as we need to to close the branch.
        if current_comment_level <= previous_comment_level:
            for i in range(0, previous_comment_level-current_comment_level+1):
                html_comments += '</div>'

        # CSS classes to be applied.
        classes = ''

        # If first-level comment, we put a margin
        if current_comment_level == 1:
            classes += 'f '

        if comments_forest[current_comment_id]['d'] == 'admin':
            classes += 'a ' # Distinguished administrator post color
        elif comments_forest[current_comment_id]['d'] == 'moderator':
            classes += 'm ' # Distinguished moderator post color
        elif comments_forest[current_comment_id]['o']:
            classes += 'p ' #  OP post color
        elif current_comment_level % 2 == 0:
            classes += 'e ' # Even post color
        else:
            classes += 'o ' # Odd post color

        # Post level
        classes += 'l'+str(current_comment_level)[-1] # only taking the last digit
        html_comments += f'<div class="{classes}" id="{current_comment_id}">'

        time_comment = datetime.datetime.fromtimestamp(comments_forest[current_comment_id]['t'])
        time_comment_str = time_comment.strftime(config["defaults"]["dateformat"])

        # Adding the comment to the list
        html_comments += f"""<header>{comments_forest[current_comment_id]['a']}, on {time_comment_str} ({comments_forest[current_comment_id]['s']}{'' if comments_forest[current_comment_id]['e'] is False else ', edited'})</header>{comment_parser(comments_forest[current_comment_id]['b'])}"""
        
        previous_comment_level = current_comment_level
        comment_counter += 1

    # Merging this all together
    html_total = html_head+html_submission+html_firstpost+html_comments
    html_total = html_total.replace('<p>', '').replace('</p>', '')

    return html_total


def write_file(content, submission, now, output_directory):
    """
    Writes the HTML content into a file. Returns the filename
    """
    # keeping the submission name in URL
    sanitized_name = submission.permalink.split('/')[-2]

    # Reducing filename to 200 characters
    sanitized_name = (sanitized_name[:150]) if len(sanitized_name) > 150 else sanitized_name
    path = os.path.join(output_directory, f"{submission.subreddit.display_name}-{sanitized_name}-{now.strftime('%Y%m%d-%H%M%S')}.html")
    filename = f"{submission.subreddit.display_name}-{sanitized_name}-{now.strftime('%Y%m%d-%H%M%S')}.html"

    f = open(path, "wb")
    f.write(content.encode('utf-8'))
    f.close()

    return filename


def myprint(message, color, stderr=False):
    """
    Easy wrapper for print
    """
    if stderr:
        print(f"{colored.fg(color)}{message}{colored.attr(0)}", file=sys.stderr)
    else:
        print(f"{colored.fg(color)}{message}{colored.attr(0)}")


# Config loading
try:
    with open(os.path.join(os.path.dirname(__file__), 'config.yml')) as f:
        config = yaml.safe_load(f)
except:
    myprint(f"[x] Cannot load config file. Make sure it exists and the syntax is correct.", 9, True)
    raise SystemExit(1)

# Test connection
try:
    reddit = connect()
except:
    myprint(f"[x] It looks like you are not authenticated well.", 9, True)
    myprint(f"[x] Please check your credentials and retry.", 9, True)
    raise SystemExit(1)

now = datetime.datetime.now(datetime.timezone.utc)
now_str = now.strftime(config["defaults"]["dateformat"])


def scrape_url(url):
    """
    Scrape a single Reddit thread
    """

    submission_id = extract_id(url)
    if submission_id is None:
        myprint(f'[x] The URL or ID "{url}" looks incorrect. Please check it.', 9, True)
        raise SystemExit(1)

    try:
        # "Connecting" to submission and getting information
        submission, nb_replies = get_submission(reddit, submission_id)
        myprint(f'[+] Submission {submission_id} found ("{submission.title}" on r/{submission.subreddit.display_name}, {nb_replies} replies), beginning download', 8)

        # Getting the comment list and comment forest
        submission, comments_index, comments_forest = download_submission(submission, submission_id)
    except prawcore.exceptions.NotFound:
        myprint(f"[x] The submission {submission_id} was not found.", 9, True)
    except prawcore.exceptions.Forbidden:
        myprint(f"[x] Not allowed to access the submission {submission_id}. That usually means the submission is on a private subreddit you do not have access to.", 9, True)
    else:
        myprint(f"[+] Submission downloaded.", 8)

    # Generating HTML structure
    while True: # allows to retry
        try:
            html = generate_html(submission, submission_id, now_str, None, comments_index, comments_forest)
        except RecursionError:
            myprint(f"[x] The HTML structure could not be generated because the structure of the replies is going too deep for the program to handle.", 9, True)
            myprint(f"[x] If you really want to save that thread, pass the --disable-recursion-limit option. Please note however that this might lead to crashing the program.", 9, True)
            raise SystemExit(1)
        else:
            break

    return html, submission


def main():
    try:
        url = input("Enter URL: ")
        html, submission = scrape_url(url)    

        myprint(f"[+] Submission structured.", 8)

        # Saving to disk
        os.makedirs("downloads", exist_ok=True)

        try:
            filename = write_file(html, submission, now, "downloads")
        except PermissionError as e:
            myprint(f"[x] Could not write file because of bad permissions.", 9, True)
            raise SystemExit(1)
        except Exception as e:
            myprint(f"[x] Uncaught problem when writing the file: {e}", 9, True)
            raise SystemExit(1)

        myprint(f"[=] Submission saved! Filename: {filename}", 10)

    except Exception as e:
        # general catch
        myprint(f"[x] Uncaught problem: {e}", 9, True)
        raise
