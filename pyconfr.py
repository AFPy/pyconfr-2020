from urllib.parse import quote
from urllib.request import urlopen
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from flask import Flask, render_template, url_for
from flask_frozen import Freezer
from markdown2 import Markdown
from sassutils.wsgi import SassMiddleware

app = Flask(__name__, static_url_path='/2020/static')
app.wsgi_app = SassMiddleware(app.wsgi_app, {
    'pyconfr': {
        'sass_path': 'static/sass',
        'css_path': 'static/css',
        'wsgi_path': '/2020/static/css',
        'strip_extension': True}})


@app.template_filter()
def slug(string):
    return quote(str(string).lower(), safe='')


@app.route('/')
@app.route('/<lang>/')
@app.route('/2020/')
@app.route('/2021/')
@app.route('/2022/')
@app.route('/2020/<lang>/')
@app.route('/2021/<lang>/')
@app.route('/2022/<lang>/')
@app.route('/2020/<lang>/<name>.html')
@app.route('/2021/<lang>/<name>.html')
@app.route('/2022/<lang>/<name>.html')
def page(name='index', lang='fr'):
    return render_template(
        '{lang}/{name}.html.jinja2'.format(name=name, lang=lang),
        page_name=name, lang=lang)


@app.route('/2020/<lang>/talks/<category>.html')
def talks(lang, category):
    talks = []
    with urlopen('https://cfp-2020.pycon.fr/schedule/xml/') as fd:
        tree = ElementTree.fromstring(fd.read().decode('utf-8'))
    for day in tree.findall('.//day'):
        for event in day.findall('.//event'):
            talk = {child.tag: child.text for child in event}
            talk['person'] = ', '.join(
                person.text for person in event.findall('.//person'))
            talk['id'] = event.attrib['id']
            talk['day'] = day.attrib['date']
            if talk['type'] != category:
                continue
            if 'description' in talk:
                talk['description'] = Markdown().convert(talk['description'])
            talks.append(talk)
    return render_template(
        '{lang}/talks.html.jinja2'.format(lang=lang),
        category=category, talks=talks, lang=lang)


@app.route('/2020/<lang>/full-schedule.html')
def schedule(lang):
    with urlopen('https://cfp-2020.pycon.fr/schedule/html/') as fd:
        html = fd.read().decode('utf-8')

    if lang == 'fr':
        html = html.replace('Room', 'Salle')
    else:
        html = (
            html
            .replace('samedi 02 novembre', 'Saturday, November 2')
            .replace('dimanche 03 novembre', 'Sunday, November 3'))
        for minute in (0, 30):
            html = html.replace(f'12:{minute:02}', f'12:{minute:02} PM')
            for hour in range(9, 12):
                html = html.replace(
                    f'{hour:02}:{minute:02}', f'{hour:02}:{minute:02} AM')
            for hour in range(13, 19):
                html = html.replace(
                    f'{hour:02}:{minute:02}',
                    f'{hour-12:02}:{minute:02} PM')

    # Delete extra cells for sprints
    html = (
        html
        .replace('colspan="9"', '')
        .replace('<td colspan="8"></td>', ''))

    # Insert links in the table
    soup = BeautifulSoup(html, 'html.parser')
    conf_colors = {
        '#ff7373': 'keynote',
        '#73cbef': 'workshop',
        '#e9b96e': 'conference',
    }
    for color, kind in conf_colors.items():
        for td in soup.find_all('td', attrs={'bgcolor': color}):
            title = list(td.children)[0]
            url = url_for('talks', lang=lang, category=kind)
            href = f'{url}#{slug(title)}'
            link = soup.new_tag('a', href=href, target='_parent')
            title.wrap(link)

    return render_template('schedule.html.jinja2', data=soup)


@app.cli.command('freeze')
def freeze():
    Freezer(app).freeze()
