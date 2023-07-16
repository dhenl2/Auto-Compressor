# Use -B flag to always make

venv:
	source ./venv/Scripts/activate

test:
	env environment="testing" pytest test/test.py

requirements: venv
	pip3 freeze > requirements.txt