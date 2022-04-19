# arxiv_scraper

This is a simple scraper script for downloading paper summaries from arXiv for the purpose of creating markdown summaries of papers within certain categories, within a certain timeframe.

The categories are defined in the categories.py file, which also includes a dictionary mapping category codes to human readable descriptions.

The script can post to reddit and always outputs a text file in markdown format. A reddit app must be configured at https://old.reddit.com/prefs/apps/ ... "Create Another App" in order to do post.

The script should be run from the command line with the following arguments:

* reddit_app_name: Reddit app name
* reddit_app_id: Reddit app internal id
* reddit_app_secret: Reddit app secret key
* reddit_user_name: Reddit user to post with
* reddit_user_password: Reddit user's password
* reddit_subreddit: Reddit subreddit to post to
* arxiv_start_date: Start date of report
* arxiv_end_date: End date of report

If any of the reddit arguments are omitted then only the text file will be generated. If the date arguments are omitted the script will grab data for the previous Monday-Sunday period.

Example usage:

python arxiv_scraper.py --reddit_app_name lampishapp --reddit_app_id 6FGcs82-ttLLPDH852TH1Q --reddit_app_secret DFGN6323hyhbHHD-963PLMTNL8612m --reddit_user_name lampishthing --reddit_user_password lampishpw --reddit_subreddit lampishsub