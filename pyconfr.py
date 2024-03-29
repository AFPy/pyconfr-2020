from urllib.error import HTTPError
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


@app.route('/<lang>/', endpoint='lang')
@app.route('/2020/', endpoint='2020')
@app.route('/2021/', endpoint='2021')
@app.route('/2022/', endpoint='2022')
@app.route('/2020/<lang>/', endpoint='2020lang')
@app.route('/2021/<lang>/', endpoint='2021lang')
@app.route('/2022/<lang>/', endpoint='2022lang')
@app.route('/2020/<lang>/<name>.html', endpoint='2020langname')
@app.route('/2021/<lang>/<name>.html', endpoint='2021langname')
@app.route('/2022/<lang>/<name>.html', endpoint='2022langname')
@app.route('/')
def page(name='index', lang='fr'):
    return render_template(
        '{lang}/{name}.html.jinja2'.format(name=name, lang=lang),
        page_name=name, lang=lang)


@app.route('/2020/<lang>/talks/<category>.html')
def talks(lang, category):
    talks = []
    try:
        with urlopen('https://cfp-2020.pycon.fr/schedule/xml/') as fd:
            tree = ElementTree.fromstring(fd.read().decode('utf-8'))
    except HTTPError:
        tree = ElementTree.fromstring("")
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
    try:
        with urlopen('https://cfp-2020.pycon.fr/schedule/html/') as fd:
            html = fd.read().decode('utf-8')
    except HTTPError:
        html = ""

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
    langs = ('fr', 'en')
    years = ('2020', '2021', '2022')
    names = ('conduct', 'news', 'schedule', 'sponsors', 'support', 'venue')

    freezer = Freezer(app)

    @freezer.register_generator
    def alternate_urls():
        for year in years:
            yield (year, {})
        for lang in langs:
            yield ('lang', {'lang': lang})
            for year in years:
                yield (year + 'lang', {'lang': lang})
                for name in names:
                    yield (year + 'langname', {'name': name, 'lang': lang})


    @freezer.register_generator
    def schedule():
        for lang in langs:
            yield {'lang': lang}

    freezer.freeze()

