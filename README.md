Login with your Spotify credentials on www.musicalwayfinder.com

# Set up a development environment (Python backend)


## Installation

Clone this repository:

```
git clone https://github.com/The-Wayfinder-Society/wayfinder-app.git
```

Ensure you are using Python 3:

```
python --version
```
(example output: `Python 3.7.3`)

Create a new Python virtual environment in the repository:

(If you are in a current conda environment, deactivate with `conda deactivate`. If you are in a current python virtual environment, deactivate with `deactivate`)

```
cd wayfinder-app
python3 -m venv environment
source environment/bin/activate
```

Confirm `python` points to the virtual envirionment:
```
which python
```
(example output: `/Users/steven/Projects/wayfinder-app/environment/bin/python`)

Install the python modules required for development:
```
python -m pip install -r requirements.txt
```

# Set up a development environment (JS backend)

## Installation

Clone this repository:

```
git clone https://github.com/The-Wayfinder-Society/wayfinder-app.git
```

Set up a conda environment (on OSX)
```
$ cd wayfinder-app
$ conda env create -p $PWD/env -f environment.osx.yaml
```
Or create the environment from scratch:
```
$ conda create -p $PWD/env
$ conda activate ./env
$ conda install -c conda-forge mamba
$ mamba install nodejs
```

Install required node modules
```
$ npm install
```

Build `bundle.js`
```
$ npm run build
```
and serve the web app:
```
$ npm run serve
```