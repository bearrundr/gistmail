"""\
GistMail

Email gist@gistmail.com with a link and get a response with that article's summary.
"""

from mandrill import Mandrill
from flask import Flask, abort, json, render_template, request
from raven.contrib.flask import Sentry
from summarize import summarize_page


# Flask application
app = Flask(__name__)
# Configuration
app.config.from_object('settings')
app.config.from_envvar('SETTINGS_MODULE', silent=True)
app.config.from_pyfile('settings_local.py', silent=True)
# Email
mandrill = Mandrill(app.config['MANDRILL_API_KEY'])
# Error logging
sentry = Sentry(app) if not app.config['SENTRY_DISABLED'] else None


# Views
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/admin')
def admin():
    if not bool(app.config['DEBUG']):
        abort(404)
    return render_template('admin.html', test_email_json=test_email_json())


@app.route('/incoming', methods=['GET', 'POST'])
def incoming():
    # Ignore initial Mandrill check
    if request.method == 'GET':
        return ''
    if not request.form['mandrill_events'] or request.form['mandrill_events'] == []:
        return ''

    print ' * INCOMING EMAIL:',

    event = json.loads(request.form['mandrill_events'])[0]
    msg = event['msg']

    email = msg['from_email']
    subject = msg['subject']
    print email

    # Ignore Mandrill test
    if email == u'example.sender@mandrillapp.com':
        return ''

    # TODO: Use pattern matching to find the URL
    url = msg['text'].strip()
    print 'Summarizing:', url

    try:
        summary = summarize_page(url)
    except Exception as ex:
        if sentry:
            sentry.captureException()
        print ' * ERROR:', type(ex), ex
        subject = '[ERROR] ' + subject
        html = render_template('error_email.html', url=url)
    else:
        html = render_template('summary_email.html',
            title=summary.title, url=summary.url, summaries=summary.summaries)

    print 'Replying to:', email
    email_id = send_email(email, subject, html)

    print 'Reply ID:', email_id
    return ''


# Helpers
def send_email(to, subject, html):
    if isinstance(to, basestring):
        to = {'email': to}
    message = {
        'html': html,
        'subject': subject,
        'from_email': app.config['MANDRILL_EMAIL'],
        'from_name': app.config['MANDRILL_EMAIL_NAME'],
        'to': [to],
    }
    result = mandrill.messages.send(message=message)[0]
    return result['_id']


def test_email_json():
    return json.dumps([
        {
            'msg': {
                'from_email': app.config['ADMIN_EMAIL'],
                'subject': 'GistMail Test',
                'text': 'http://gistmail.com',
            },
        },
    ], indent=4, sort_keys=True)


# Run development server
if __name__ == '__main__':
    app.run(app.config['HOST'], app.config['PORT'], app.debug)
