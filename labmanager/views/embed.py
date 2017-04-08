import traceback
import requests
from bs4 import BeautifulSoup
from flask import Blueprint, render_template, make_response, redirect, url_for, request, session, jsonify
from labmanager.views.authn import requires_golab_login, current_golab_user

from labmanager.db import db
from labmanager.babel import gettext, lazy_gettext
from labmanager.models import EmbedApplication, EmbedApplicationTranslation
from labmanager.rlms import find_smartgateway_link
from labmanager.translator.languages import obtain_languages

from flask.ext.wtf import Form
from wtforms import TextField, HiddenField, SelectMultipleField
from wtforms.validators import required
from wtforms.fields.html5 import URLField
from wtforms.widgets import HiddenInput, TextInput, CheckboxInput, html_params, HTMLString
from wtforms.widgets.html5 import URLInput

embed_blueprint = Blueprint('embed', __name__)

@embed_blueprint.context_processor
def inject_variables():
    return dict(current_golab_user=current_golab_user())

class AngularJSInput(object):
    def __init__(self, **kwargs):
        self._internal_kwargs = kwargs
        super(AngularJSInput, self).__init__()

    # Support render_field(form.field, ng_value="foo")
    # http://stackoverflow.com/questions/20440056/custom-attributes-for-flask-wtforms
    def __call__(self, field, **kwargs):
        for key in list(kwargs):
            if key.startswith('ng_'):
                kwargs['ng-' + key[3:]] = kwargs.pop(key)

        for key in list(self._internal_kwargs):
            if key.startswith('ng_'):
                kwargs['ng-' + key[3:]] = self._internal_kwargs[key]

        return super(AngularJSInput, self).__call__(field, **kwargs)

class AngularJSTextInput(AngularJSInput, TextInput):
    pass

class AngularJSURLInput(AngularJSInput, URLInput):
    pass

class AngularJSHiddenInput(AngularJSInput, HiddenInput):
    pass


class DivWidget(object):
    def __init__(self, padding = '10px'):
        self.padding = padding

    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        html = ['<div %s>' % (html_params(**kwargs))]
        for subfield in field:
            html.append('<label class="checkbox-inline">%s %s</label>' % (subfield(), subfield.label.text))
        html.append('</div>')
        return HTMLString(''.join(html))


class MultiCheckboxField(SelectMultipleField):
    widget = DivWidget()
    option_widget = CheckboxInput()

# 
# Public URLs
# 

@embed_blueprint.route('/apps/')
def apps():
    applications = db.session.query(EmbedApplication).order_by(EmbedApplication.last_update).all()
    return render_template("embed/apps.html", user = current_golab_user(), applications = applications, title = gettext("List of applications"))

@embed_blueprint.route('/apps/<identifier>/')
def app(identifier):
    application = db.session.query(EmbedApplication).filter_by(identifier = identifier).first()
    if application is None:
        return render_template("embed/error.html", message = gettext("Application '{identifier}' not found").format(identifier=identifier), user = current_golab_user()), 404

    return render_template("embed/app.html", user = current_golab_user(), app = application, title = gettext("Application {name}").format(name=application.name))

@embed_blueprint.route('/apps/<identifier>/app.html')
def app_html(identifier):
    application = db.session.query(EmbedApplication).filter_by(identifier = identifier).first()
    if application is None:
        return jsonify(error=True, message="App not found")

    apps_per_language = {
        'en': application.url,
    }
    for translation in application.translations:
        apps_per_language[translation.language] = translation.url

    return render_template("embed/app-embedded.html", apps=apps_per_language)

@embed_blueprint.route('/apps/<identifier>/app.xml')
def app_xml(identifier):
    application = db.session.query(EmbedApplication).filter_by(identifier = identifier).first()
    if application is None:
        return render_template("embed/error.xml", user = current_golab_user(), message = gettext("Application '{identifier}' not found").format(identifier=identifier)), 404

    apps_per_language = {}
    languages = ['en']
    for translation in application.translations:
        apps_per_language[translation.language] = translation.url
        languages.append(translation.language)

    author = application.owner.display_name
    print author

    response = make_response(render_template("embed/app.xml", author = author, user = current_golab_user(), identifier=identifier, app = application, languages=languages, apps_per_language = apps_per_language, title = gettext("Application {name}").format(name=application.name)))
    response.content_type = 'application/xml'
    return response

# 
# Management URLs
# 

@embed_blueprint.route('/')
@requires_golab_login
def index():
    applications = db.session.query(EmbedApplication).filter_by(owner = current_golab_user()).order_by(EmbedApplication.last_update).all()
    return render_template("embed/index.html", applications = applications, user = current_golab_user())

class SimplifiedApplicationForm(Form):
    name = TextField(lazy_gettext("Name:"), validators=[required()], widget = AngularJSTextInput(ng_model='embed.name', ng_enter="submitForm()"), description=lazy_gettext("Name of the resource"))
    age_ranges_range = HiddenField(lazy_gettext("Age ranges:"), validators=[required()], description=lazy_gettext("Select the age ranges this tool is useful for"))

    # The following are NOT REQUIRED
    description = TextField(lazy_gettext("Description:"), validators=[], widget = AngularJSTextInput(ng_model='embed.description', ng_enter="submitForm()"), description=lazy_gettext("Describe the resource in a few words"))
    domains_text = TextField(lazy_gettext("Domains:"), validators=[], widget = AngularJSTextInput(ng_enter="submitForm()"), description=lazy_gettext("Say in which domains apply to the resource (separated by commas): e.g., physics, electronics..."))

    url = URLField(lazy_gettext("Web:"), widget = AngularJSURLInput(ng_model='embed.url', ng_enter="submitForm()"), description=lazy_gettext("Web address of the resource"))
    height = HiddenField(lazy_gettext("Height:"), widget = AngularJSHiddenInput(ng_model='embed.height'))
    scale = HiddenField(lazy_gettext("Scale:"), widget = AngularJSHiddenInput(ng_model='embed.scale'))


class ApplicationForm(SimplifiedApplicationForm):
    url = URLField(lazy_gettext("Web:"), validators=[required()], widget = AngularJSURLInput(ng_model='embed.url', ng_enter="submitForm()"), description=lazy_gettext("Web address of the resource"))
    height = HiddenField(lazy_gettext("Height:"), validators=[required()], widget = AngularJSHiddenInput(ng_model='embed.height'))
    scale = HiddenField(lazy_gettext("Scale:"), validators=[required()], widget = AngularJSHiddenInput(ng_model='embed.scale'))

def obtain_formatted_languages(existing_language_codes):
    languages = [ (lang.split('_')[0], name) for lang, name in obtain_languages().items() if lang != 'en_ALL' and name != 'DEFAULT']

    return [ { 'code' : language, 'name' : name } for language, name in languages if language not in existing_language_codes]

def list_of_languages():
    return { key.split('_')[0] : value for key, value in obtain_languages().items() }
        
def _get_scale_value(form):
    if form.scale.data:
        try:
            scale = int(100 * float(form.scale.data))
        except ValueError:
            pass
        else:
            form.scale.data = unicode(scale)
            return scale
    return None

def get_url_metadata(url, timeout = 3):
    name = ''
    description = ''
    code = None
    x_frame_options = ''
    error_retrieving = False
    content_type = ''
    try:
        req = requests.get(url, timeout=(timeout, timeout), stream=True)
    except:
        traceback.print_exc()
        error_retrieving = True
    else:
        try:
            code = req.status_code
            x_frame_options = req.headers.get('X-Frame-Options', '').lower()
            content_type = req.headers.get('content-type', '').lower()
            if req.status_code == 200 and 'html' in req.headers.get('content-type', '').lower():
                # First megabyte maximum
                content = req.iter_content(1024 * 1024).next()
                soup = BeautifulSoup(content, 'lxml')
                name = (soup.find("title").text or '').strip()
                meta_description = soup.find("meta", attrs={'name': 'description'})
                if meta_description is not None:
                    meta_description_text = meta_description.attrs.get('content')
                    if meta_description_text:
                        description = (meta_description_text or '').strip()
            req.close()
        except:
            traceback.print_exc()

    return { 'name' : name, 'description': description, 'code': code, 'x_frame_options' : x_frame_options, 'error_retrieving' : error_retrieving, 'content_type' : content_type }


@embed_blueprint.route('/create', methods = ['GET', 'POST'])
@requires_golab_login
def create():
    original_url = request.args.get('url')
    if original_url:
        bookmarklet_from = original_url
    else:
        bookmarklet_from = None

    original_application = None
    if original_url:
        applications = db.session.query(EmbedApplication).filter_by(url=original_url).all()
        if applications:
            original_application = applications[0]
            for app in applications:
                if len(app.translations) > len(original_application.translations):
                    original_application = app
                if app.name and not original_application.name:
                    original_application = app
                    continue
                if app.description and not original_application.description:
                    original_application = app
                    continue

    if original_application is not None:
        form = ApplicationForm(obj=original_application)
    else:
        form = ApplicationForm()

    if not form.url.data and original_url:
        form.url.data = original_url
        if not form.name.data:
            result = get_url_metadata(original_url, timeout = 5)
            if result['name']:
                form.name.data = result['name']
            if result['description'] and not form.description.data:
                form.description.data = result['description']

    if form.validate_on_submit():
        form_scale = _get_scale_value(form)
        application = EmbedApplication(url = form.url.data, name = form.name.data, owner = current_golab_user(), height=form.height.data, scale=form_scale, description=form.description.data, age_ranges_range = form.age_ranges_range.data)
        application.domains_text = form.domains_text.data
        db.session.add(application)
        try:
            db.session.commit()
        except Exception as e:
            traceback.print_exc()
            return render_template("embed/error.html", message = gettext("There was an error creating an application"), user = current_golab_user()), 500
        else:
            kwargs = {}
            if bookmarklet_from:
                kwargs['url'] = bookmarklet_from
            return redirect(url_for('.edit', identifier=application.identifier, **kwargs))
            
    return render_template("embed/create.html", form=form, header_message=gettext("Add a web"), user = current_golab_user(), bookmarklet_from=bookmarklet_from, create=True, edit=False)

@embed_blueprint.route('/check.json')
def check_json():
    url = request.args.get('url')
    if not url:
        return jsonify(error=True, message=gettext("No URL provided"), url=url)
    if not url.startswith(('http://', 'https://')):
        return jsonify(error=True, message=gettext("URL doesn't start by http:// or https://"), url=url)
    
    if url == 'http://':
        return jsonify(error=False, url=url)

    sg_link = find_smartgateway_link(url, request.referrer)
    if sg_link:
        return jsonify(error=False, sg_link=sg_link, url=url)
    
    metadata = get_url_metadata(url, timeout = 5)
    if metadata['error_retrieving']:
        return jsonify(error=True, message=gettext("Error retrieving URL"), url=url)

    if metadata['code'] != 200:
        return jsonify(error=True, message=gettext("Error accessing to the URL"), url=url)

    if metadata['x_frame_options'] in ('deny', 'sameorigin') or metadata['x_frame_options'].startswith('allow'):
        return jsonify(error=True, message=gettext("This website does not support being loaded from a different site, so it is unavailable for Go-Lab"), url=url)
    
    if 'html' not in metadata['content_type']:
        if 'shockwave' in metadata['content_type'] or 'flash' in metadata['content_type']:
            return jsonify(error=False, url=url)

        return jsonify(error=True, message=gettext("URL is not HTML"), url=url)

    return jsonify(error=False, url=url, name = metadata['name'], description = metadata['description'])

@embed_blueprint.route('/edit/<identifier>/', methods = ['GET', 'POST'])
@requires_golab_login
def edit(identifier):
    existing_languages = {
        # lang: {
        #     'code': 'es',
        #     'name': 'Spanish',
        #     'url': 'http://....'
        # }
    }
    existing_languages_db = {
        # lang: db_instance
    }
    all_languages = list_of_languages()
    
    # Obtain from the database
    application = db.session.query(EmbedApplication).filter_by(identifier = identifier).first()
    if application is None:
        return "Application does not exist", 404

    for translation in application.translations:
        existing_languages_db[translation.language] = translation
        existing_languages[translation.language] = {
            'code': translation.language,
            'name': all_languages.get(translation.language) or 'Language not supported anymore',
            'url': translation.url
        }
    
    # languages added by the UI
    posted_languages = {
        # 'es' : 'http://.../'
    }

    if request.method == 'POST':
        for key in request.form:
            if key.startswith('language.'):
                lang_code = key[len('language.'):]
                if lang_code in all_languages:
                    posted_languages[lang_code] = request.form[key]
                

    form = ApplicationForm(obj=application)
    if form.validate_on_submit():
        # Check for new ones or changed
        for posted_language, url in posted_languages.items():
            if posted_language in existing_languages_db:
                translation = existing_languages_db[posted_language]
                if translation.url != url: # Don't trigger unnecessary UPDATEs
                    translation.url = url
            else:
                translation = EmbedApplicationTranslation(embed_application = application, url=url, language=posted_language)
                db.session.add(translation)

        # Delete old ones
        for existing_language, translation in existing_languages_db.items():
            if existing_language not in posted_languages:
                existing_languages.pop(existing_language)
                db.session.delete(translation)

        form_scale = _get_scale_value(form)
        application.update(url=form.url.data, name=form.name.data, height=form.height.data, scale=form_scale, age_ranges_range=form.age_ranges_range.data, description=form.description.data, domains_text=form.domains_text.data)
        db.session.commit()
    
        # TODO: does this still make sense?
        # if request.form.get('action') == 'publish':
        #     return _post_contents(app_to_json(application), application.url)

    # Add the posted languages to the existing ones
    for lang_code, url in posted_languages.items():
        existing_languages[lang_code] = {
            'code' : lang_code,
            'name' : all_languages[lang_code],
            'url' : url
        }

    # Obtain the languages formatted as required but excluding those already added
    languages = obtain_formatted_languages(existing_languages)
    bookmarklet_from = request.args.get('url')
    return render_template("embed/create.html", user = current_golab_user(), form=form, identifier=identifier, header_message=gettext("Edit web"), languages=languages, existing_languages=list(existing_languages.values()), all_languages=all_languages, bookmarklet_from=bookmarklet_from, edit=True, create=False)

from labmanager.views.repository import app_to_json
