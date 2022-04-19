"""Originally authored by James Mac Hale 2022. See LICENSE file for licensing details."""

import requests
from datetime import date, timedelta
from time import sleep
from lxml import etree as et
import logging
import argparse

from categories import TARGET_CATEGORIES, CATEGORY_LOOKUPS

def clean_wrapped_text(text: str):
    """Cleans up strings retrieved from arXiv that may have been wrapped across lines in the xml."""
    output = text.replace('\n', ' ')
    for _ in range(4):
        output = output.replace('  ', ' ')
    return output.strip()

def start_end_dates():
    """Returns the ISO date strings for last week's Monday & Sunday"""
    end_date = date.today() - timedelta(date.today().weekday() + 1)
    start_date = (end_date - timedelta(6)).isoformat()
    end_date = end_date.isoformat()
    start_date_cutoff = start_date
    end_date_cutoff = end_date
    return start_date, end_date

def retrieve_arxiv_data(target_categories, start_date, per_page=100, sleep_timeout=2):
    """Create the reddit post text from the list of papers.
    :param target_categories: A set arXiv categories of interest. These are the categories that will be downloaded..
    :param start_date: The first date for which to capture papers.
    :param per_page: The number of results to get per HTTP request.
    :param sleep_timeout: the timeout between requests.
    """
    arxiv_papers = list()
    i = 0

    logging.info(f'Downloading {per_page} results per batch, back to {start_date}.')
    while True:
        logging.info(f'Batch {i}...')
        response = requests.get(
            r'http://export.arxiv.org/api/query' +
            f'?search_query=' + '+OR+'.join([f'cat:{x}' for x in target_categories]) +
            f'&start={i*per_page}' +
            f'&max_results={per_page}' +
            f'&sortBy=lastUpdatedDate' +
            '&sortOrder=descending')
        i = i + 1
        root = et.fromstring(response.content)

        for x in root.findall('./entry', namespaces=root.nsmap):
            cats = {
                    *{x.find('./primary_category', namespaces={None: 'http://arxiv.org/schemas/atom'}).attrib['term']},
                    *{y.attrib['term'] for y in x.findall('./category', namespaces=root.nsmap)}
                }
            if len(target_categories.intersection(cats))>0:
                arxiv_papers.append({
                    'Authors': [y.text for y in x.findall('./author/', namespaces={None: 'http://www.w3.org/2005/Atom'})],
                    'Title': clean_wrapped_text(x.find('./title', namespaces={None: 'http://www.w3.org/2005/Atom'}).text),
                    'Updated': clean_wrapped_text(x.find('./updated', namespaces={None: 'http://www.w3.org/2005/Atom'}).text[:10]),
                    'Published': clean_wrapped_text(x.find('./published', namespaces={None: 'http://www.w3.org/2005/Atom'}).text[:10]),
                    'Categories': cats,
                    'Summary': clean_wrapped_text(x.find('./summary', namespaces={None: 'http://www.w3.org/2005/Atom'}).text),
                    'Pdf Link': (x.find('./link[@title="pdf"]', namespaces={None: 'http://www.w3.org/2005/Atom'}).attrib['href']),
                })
        if arxiv_papers[-1]['Updated'] < start_date:
            logging.info(f"Breaking at a result dated {arxiv_papers[-1]['Updated']}.")
            break
        else:
            sleep(sleep_timeout)
    return arxiv_papers

def markdown_text(arxiv_papers, category_lookups, start_date, end_date):
    """Create the reddit post text from the list of papers.
    :param arxiv_papers: A list of dictionaries of arXiv papers.
    :param category_lookups: A dictionary mapping arXiv categories to a human readable name.
    :param start_date: The first date for which to capture papers.
    :param end_date: The last date for which to capture papers.
    """

    logging.info('Creating markdown text.')
    text_output = list()
    title = f'Quant Finance Arxiv submissions {start_date} - {end_date}'
    text_output.append(f'# {title}')
    text_output.append('This is your weekly snap of quant finance submissions to the Arxiv. Papers are sorted in reverse chronological order of the *original* publication date. i.e. the newest papers are at the top, revisions are lower down the list.')
    text_output.append("If any paper take your fancy, you're encouraged to submit a link post to the subreddit, and start the discussion in the comments. Or in this thread, what do I care I'm not your boss.")

    category_papers = list()
    for paper in sorted(arxiv_papers, key=lambda d: d['Published'], reverse=True):
        if start_date <= paper['Updated'] and end_date > paper['Updated']:
            category_papers.append(paper)
            text_output.append(f"### {paper['Title']}")
            text_output.append(f"**Authors**: {', '.join(paper['Authors'])}")
            text_output.append(f"**Categories**: {', '.join([category_lookups[c] for c in paper['Categories'] if c in category_lookups])}")
            text_output.append(f"**PDF**: {paper['Pdf Link']}")
            text_output.append(f"**Dates**: originally published: {paper['Published']}, updated: {paper['Updated']}")
            text_output.append(f"**Summary**: {paper['Summary']}")
            text_output.append('')

    return title, '\n\n'.join(text_output)

def reddit_authorize(app_name, app_id, app_secret, user_name, user_password):

    logging.info('Authorizing reddit requests.')
    auth = requests.auth.HTTPBasicAuth(app_id, app_secret)

    # here we pass our login method (password), username, and password
    data = {'grant_type': 'password',
            'username': user_name,
            'password': user_password}

    # setup our header info, which gives reddit a brief description of our app
    headers = {'User-Agent': f'{app_name}/0.0.1'}

    # send our request for an OAuth token
    res = requests.post('https://www.reddit.com/api/v1/access_token',
                        auth=auth, data=data, headers=headers)

    res.raise_for_status()

    # convert response to JSON and pull access_token value
    TOKEN = res.json()['access_token']

    # add authorization to our headers dictionary
    headers = {**headers, **{'Authorization': f"bearer {TOKEN}"}}

    return headers

def reddit_submit_post(headers, app_id, subreddit, title, text):
    url = "https://oauth.reddit.com/api/submit"
    params = {
        'ad': False,
        'app': app_id,
        # 'flair_id':,
        'kind': 'self',
        'nsfw': False,
        'sr': subreddit,
        'title': title,
    }

    logging.info('Submitting post to reddit.')
    res = requests.post(url=url, headers=headers, params=params, data={'text': text.encode('utf-8')})
    res.raise_for_status()
    logging.debug(f'The submission received the following response:\n\n{res.text}')

def main(target_categories, category_lookups, reddit_data, start_date, end_date):
    """Download arXiv papers and create a reddit post text of the content.
    :param target_categories: A set arXiv categories of interest. These are the categories that will be downloaded..
    :param category_lookups: A dictionary mapping arXiv categories to a human readable name.
    """

    if start_date is None or end_date is None:
        logging.info('Start date or end date not populated, reporting last week\'s papers.')
        start_date, end_date = start_end_dates()

    arxiv_papers = retrieve_arxiv_data(target_categories, start_date, 100, 2)

    post_title, post_text = markdown_text(arxiv_papers, category_lookups, start_date, end_date)

    if all(v is not None for v in reddit_data.values()):
        reddit_headers = reddit_authorize(
            app_name = reddit_data['app_name'],
            app_id = reddit_data['app_id'],
            app_secret = reddit_data['app_secret'],
            user_name = reddit_data['user_name'],
            user_password = reddit_data['user_password']
        )

        reddit_submit_post(reddit_headers, reddit_data['app_id'], reddit_data['subreddit'], post_title, post_text)
    else:
        logging.info('Some reddit info was missing, skipping reddit post.')

    file_name = f'arxiv_submissions_{start_date}_{end_date}.md'
    logging.info(f'Saving markdown text to {file_name}.')
    with open(file_name, 'w', encoding='utf-8') as f:
        f.write(post_text)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    parser = argparse.ArgumentParser(description='Download arXiv submission metadata and summarize in markdown.')
    parser.add_argument('--reddit_app_name', type=str, help='Reddit app name.')
    parser.add_argument('--reddit_app_id', type=str, help='Reddit app internal id.')
    parser.add_argument('--reddit_app_secret', type=str, help='Reddit app secret key.')
    parser.add_argument('--reddit_user_name', type=str, help='Reddit user to post with.')
    parser.add_argument('--reddit_user_password', type=str, help='Reddit user\'s password.')
    parser.add_argument('--reddit_subreddit', type=str, help='Reddit subreddit to post to.')
    parser.add_argument('--arxiv_start_date', type=str, help='Start date of report.')
    parser.add_argument('--arxiv_end_date', type=str, help='End date of report.')
    args = parser.parse_args()

    reddit_data = {
		"app_name": args.reddit_app_name,
		"app_id": args.reddit_app_id,
		"app_secret": args.reddit_app_secret,
		"user_name": args.reddit_user_name,
		"user_password": args.reddit_user_password,
		"subreddit": args.reddit_subreddit
	}

    for k, v in reddit_data.items():
        logging.debug(f"{k}: {v}")

    main(TARGET_CATEGORIES, CATEGORY_LOOKUPS, reddit_data, args.arxiv_start_date, args.arxiv_end_date)
