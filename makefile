venv:
	source venv/Script/activate

test:
	env environment="testing" pytest test/test.py

requirements: venv
	pip3 freeze > requirements.txt