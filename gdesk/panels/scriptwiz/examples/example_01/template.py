# https://palletsprojects.com/p/jinja/
# Jinja2 is a full-featured template engine for Python
# Using it here to template Python code

def func1():
    grabs = len(idminst.grabber.keys())

    {% for row in tabulated_items -%}
    print('{{row.name}}', '{{row.value}}')
    {% endfor %}

def main(caller_argument):
    print('{{single_line_text}}')
    print("""{{multi_line_text}}""")
    print('{{some_file}}')
