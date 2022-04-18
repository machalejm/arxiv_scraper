"""Originally authored by James Mac Hale 2022. See LICENSE file for licensing details."""

import requests
from datetime import date, timedelta
from time import sleep
from lxml import etree as et
import logging

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

def retrieve_arxiv_data(target_categories, start_date, per_page=20, sleep_timeout=2):
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

def reddit_post_text(arxiv_papers, category_lookups, start_date, end_date):
    """Create the reddit post text from the list of papers.
    :param arxiv_papers: A list of dictionaries of arXiv papers.
    :param category_lookups: A dictionary mapping arXiv categories to a human readable name.
    :param start_date: The first date for which to capture papers.
    :param end_date: The last date for which to capture papers.
    """

    logging.info('Creating reddit post text.')
    text_output = list()
    text_output.append(f'# Quant Finance Arxiv submissions {start_date} - {end_date}')
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

    return '\n\n'.join(text_output)

def main(target_categories, category_lookups):
    """Download arXiv papers and create a reddit post text of the content.
    :param target_categories: A set arXiv categories of interest. These are the categories that will be downloaded..
    :param category_lookups: A dictionary mapping arXiv categories to a human readable name.
    """
    start_date, end_date = start_end_dates()

    arxiv_papers = retrieve_arxiv_data(target_categories, start_date, 20, 2)

    post_text = reddit_post_text(arxiv_papers, category_lookups, start_date, end_date)

    file_name = f'arxiv_submissions_{start_date}_{end_date}.md'
    logging.info(f'Saving reddit post text to {file_name}.')
    with open(file_name, 'w', encoding='utf-8') as f:
        f.write(post_text)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    main(TARGET_CATEGORIES, CATEGORY_LOOKUPS)
