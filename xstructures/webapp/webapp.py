#!/usr/bin/env python
import os
import time
import numpy as np
from pathlib import Path

from flask import (Flask, redirect, url_for, render_template, flash,
                   request, session, Response, send_from_directory)
from werkzeug.utils import secure_filename

from .. import get_amcsd, cif_cluster, cif2feffinp
from xraydb import atomic_number
from xraydb.chemparser import chemparse

top =  Path(__file__).absolute().parent

app = Flask('xstructures',
            static_folder=Path(top, 'static'),
            template_folder=Path(top, 'templates'))


UPLOAD_FOLDER = '/Users/Newville/tmp'
ALLOWED_EXTENSIONS = {'txt', 'cif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2**24
app.secret_key = 'persuasive butternut lanterns'

app.config.from_object(__name__)

cifdb = config = None

def connect(session, cifid=None):
    global cifdb, config
    if cifdb is None:
        cifdb = get_amcsd()

    if config is None:
        config = {'cifid': None, 'ciffile': '',
                   'mode': 'browse',
                   'mineral': '',
                   'elems_in': '',
                   'elems_out': '',
                   'strict': True,
                   'cifdict': {},
                   'atoms': [],
                   'with_h': False,
                   'edges': ['K', 'L3', 'L2', 'L1', 'M5', 'M4', 'M3'],
                   'cluster_size': 7.0,
                   'cif_cluster' :None,
                   'ciftext' : '',
                   'all_sites': {},
                   'absorber': '',
                   'edge': '',
                   'cif_link': None,
                   'feff_links': {},
                   'fdmnes_fname': '',
        }
    if cifid is None:
        config['mode'] = 'browse'
        config['cif_link'] = None
        config['feff_links'] = {}
        config['fdmnes_fname'] = ''

    else:
        if '.' in cifid or '.cif' in cifid or '.txt' in cifid:
            config['mode'] = 'file'
        else:
            try:
                cifid = int(cifid)
                config['mode'] = 'amsid'
            except ValueError:
                config['mode'] = 'file'

    if config['mode'] == 'amsid':
        config['cifffile'] = ''
        config['cifid'] = int(cifid)
        cif = cifdb.get_cif(cifid)
        config['ciftext'] = cif.ciftext.strip()
    elif config['mode'] == 'file':
        config['ciffile'] = cifid
        config['cifid'] = cifid
        config['cif_link'] = None
        config['feff_links'] = {}
        config['cifdict'] = {}
        config['fdmnes_fname'] = ''
        with open(Path(app.config["UPLOAD_FOLDER"], cifid).absolute(), 'r') as fh:
            config['ciftext'] = fh.read()



def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'ixas_logo.ico',
                               mimetype='image/vnd.microsoft.icon')

@app.route('/')
@app.route('/', methods=['GET', 'POST'])
@app.route('/<cifid>', methods=['GET', 'POST'])
def index(cifid=None):
    global cifdb, config
    connect(session, cifid=cifid)

    # print(f"INDEX cifid {cifid}  filename {config['ciffile']}, {len(config['ciftext'])}")

    if len(config['ciftext']) > 3:
        cluster = cif_cluster(config['ciftext'])

        config['atoms'] = []
        config['cif_link'] = None
        config['feff_links'] = {}
        config['all_sites'] = cluster.all_sites

        for at in chemparse(cluster.formula.replace(' ', '')):
            if at not in ('H', 'D') and at not in config['atoms']:
                config['atoms'].append(at)

    if request.method == 'POST':
        if 'search' in request.form.keys():
            mineral = request.form.get('mineral')
            elems_in = request.form.get('elems_in').strip()
            elems_out = request.form.get('elems_out').strip()
            strict = request.form.get('strict') is not None
            config.update({'elems_in': elems_in, 'elems_out': elems_out,
                           'mineral': mineral, 'strict': strict})
            if len(mineral) > 2 and not mineral.endswith('*'):
                mineral = mineral + '*'

            contains_elements = excludes_elements = None
            if len(elems_in) >  0:
                contains_elements = [a.strip().title() for a in elems_in.split(',')]
            if len(elems_out) >  0:
                excludes_elements = [a.strip().title() for a in elems_out.split(',')]

            cifdict = {}
            all_cifs = cifdb.find_cifs(mineral_name=mineral,
                                       contains_elements=contains_elements,
                                       excludes_elements=excludes_elements,
                                       strict_contains=strict, max_matches=500)

            for cif in all_cifs:
                try:
                    label = cif.formula.replace(' ', '')
                    mineral = cif.get_mineralname()
                    year = cif.publication.year
                    journal= cif.publication.journalname
                    cid = cif.ams_id
                    label = f'{label}: {mineral}'
                    cite = f'{journal} {year}'
                    if len(label) > 80 and len(cifict) > 125:
                        continue
                    cifdict[cid] = (label, cite)
                except:
                    print("could not add cif ", cif)
            config['cifdict'] = cifdict
            config['cifid'] = cifid  = None
            config['ciftext'] = ''
            config['ciffile']  = ''
            config['atoms'] = []
            config['cif_link'] = None
            config['feff_links'] = {}


        elif 'feff' in request.form.keys():
            config['absorber'] = absorber = request.form.get('absorbing_atom')
            config['edge'] = edge =request.form.get('edge')
            config['with_h'] = with_h = 1 if request.form.get('with_h') else 0
            config['cluster_size'] = cluster_size = request.form.get('cluster_size')

            if config['ciftext'] is not None:
                cluster = cif_cluster(config['ciftext'])
                config['all_sites'] = cluster.all_sites
                cifid = config['cifid']
                if config['ciffile'] not in ('', None, 'None'):
                    cifid = config['ciffile']
                elif config['cifid'] is not None:
                    cifid = config['cifid']
                    config['cif_link'] = (f'AMSCD_{cifid}.cif', cifid)
                config['feff_links'] = {}
                for slabel, sindex in config['all_sites'][absorber].items():
                    link = f'feff_{cifid}_{absorber}{sindex}_{edge}.inp'
                    config['feff_links'][link] = (slabel, cifid, absorber, edge, sindex,
                                                  cluster_size, with_h)

    return render_template('index.html', **config)


@app.route('/feffinp/<cifid>/<absorber>/<site>/<edge>/<cluster_size>/<with_h>/<fname>')
def feffinp(cifid=None, absorber=None, site=1, edge='K', cluster_size=7.0,
            with_h=False, fname=None):
    connect(session, cifid)
    global cifdb, config
    if absorber.startswith('Wat'):
        absorber.replace('Wat', 'O')
    if absorber.startswith('O-H'):
        absorber.replace('O-H', 'O')
    if absorber.startswith('D') and not absorber.startswith('Dy'):
        absorber.replace('D', 'H')

    try:
        stoich = chemparse(absorber)
    except ValueError:
        if ( ('M' in absorber)
             and (not absorber.startswith('Mo'))
             and (not absorber.startswith('Mn'))):
            try:
                stoich = chemparse(absorber[:].replace('M', ''))
            except:
                stoich = {}

    if len(stoich) != 1:
        txt = f"could not parse absorber: '{absorber}' for CIF {cifid}  {stoich}"
    else:
        try:
            xcifid = int(cifid)
        except:
            xcifid = None

        absorber = list(stoich.keys())[0]
        feffinp = cif2feffinp(config['ciftext'], absorber, edge=edge,
                    cluster_size=float(cluster_size), cifid=xcifid,
                    with_h=with_h, absorber_site=int(site))

    return Response(feffinp, mimetype='text/plain')


@app.route('/ciffile/<cifid>/<fname>')
def ciffile(cifid=None, fname='amcsd.cif'):
    connect(session, cifid)
    global cifdb, config
    return Response(config['ciftext'], mimetype='text/plain')
#
#

# @app.route('/ciffile/<name>')
# def ciffile(name=None):
#     connect(session)
#     global cifdb, config
#
#     print('use uploadedCIF  ', name)
#     fname = Path(app.config["UPLOAD_FOLDER"], name).absolute().as_posix()
#     with open(fname, 'r') as fh:
#         ciftext = fh.read()
#
#     cluster = cif_cluster(ciftext)
#     config['ciftext'] = f"\n{ciftext.strip()}"
#     config['atoms'] = []
#     config['xtal_sites'] = ['']
#     config['xtal_site'] = ''
#     config['all_sites'] = cluster.all_sites
#
#     for at in chemparse(cif.formula.replace(' ', '')):
#         if at not in ('H', 'D') and at not in config['atoms']:
#             config['atoms'].append(at)
#
#     if len(config['atoms']) > 0:
#         config['xtal_sites'] = list(cluster.all_sites[config['atoms'][0]].keys())
#         config['xtal_site'] =  config['xtal_sites'][0]


@app.route('/upload/')
def upload():
    return render_template('upload.html')



@app.route('/upload_cif', methods=['GET', 'POST'])
def upload_cif():
    connect(session)
    if request.method == 'POST':
        # print("METHOD POST" , request)

        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('index', cifid=filename))
    return render_template('upload.html')



@app.route('/about/')
def about():
    return render_template('about.html')
