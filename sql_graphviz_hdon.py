#!/usr/bin/env python

import sys, hashlib
from datetime import datetime
from pyparsing import alphas, alphanums, Literal, Word, Forward, OneOrMore, ZeroOrMore, CharsNotIn, Suppress, QuotedString, Optional, delimitedList, removeQuotes

def dprint(*args):
    print(*args, file=sys.stderr)

def extract_name_from_field(field):
    field_name = field.split(' ')[0]
    if field_name[0] == '`':
        field_name = field_name[1:-1]
    dprint('field name', field_name)
    return field_name

def field_act(s, loc, tok):
    return {
        'type': 'field',
        'port': extract_name_from_field(tok[0].replace('"', '')),
        'the_rest': extract_name_from_field(tok[1].replace('"', '\\"'))
    }

def field_list_act(s, loc, tok):
    return "\n        ".join(tok)

def create_table_act(s, loc, tok):
    tableName = tok['tableName']
    table_parts = tok['table_parts']
    #dprint('table_parts=', table_parts)
    fields = '\n'.join([
        field_row(field) for field in table_parts if field['type'] == 'field'
    ])
    fk_edges = '\n'.join([
        fk_edge(dict(tableName=tableName, **fk)) for fk in table_parts if fk['type'] == 'fk'
    ])
    #dprint('fields=', fields)
    #dprint('fk_edges=', fk_edges)
    return '''
  "{tableName}" [
    shape=none
    label=<
      <table border="0" cellspacing="0" cellborder="1">
        <tr><td bgcolor="chartreuse1"><font face="Times-bold" point-size="20">{tableName}</font></td></tr>
        {fields}
      </table>
    >];
    {fk_edges}
    '''.format(
        tableName = tableName,
        fields = fields,
        fk_edges = fk_edges,
    )


def edge_color(t1, f1, t2, f2):
    s = '%s-%s-%s-%s' % (t1, f1, t2, f2)
    h = hashlib.md5(s.encode('utf-8')).hexdigest()[0:6]
    n = int(h, 16) & 0x888888
    return '#%06x' % n


def add_fkey_act(s, loc, tok):
    color = edge_color(tok['tableName'], tok['keyName'], tok['fkTable'], tok['fkCol'])
    return '  "{tableName}":{keyName} -> "{fkTable}":{fkCol} [color="{color}"]'.format(color=color, **tok)

def foreign_key_constraint_act(s, loc, tok):
    return {
        'type': 'fk',
        'keyName': tok['localColumnNames'][1:-1],
        'fkTable': tok['foreignTableName'],
        'fkCol': tok['foreignColumnNames'][1:-1]
    }

def other_statement_act(s, loc, tok):
    return ""

def parens(x):
    return Literal("(") + x + Literal(")")

def field_row(field_data):
    #dprint('lol', field_data)
    return '<tr><td bgcolor="grey96" align="left" port="{0}"><font face="Times-bold">{0}</font>  <font color="#535353">{1}</font></td></tr>'.format(field_data['port'].replace('"', ''), field_data['the_rest'])

def fk_edge(fk_data):
    #dprint('lel', fk_data)
    color = edge_color(fk_data['tableName'], fk_data['keyName'], fk_data['fkTable'], fk_data['fkCol'])
    return '  "{tableName}":{keyName} -> "{fkTable}":{fkCol} [color="{color}"]'.format(
        color=color,
        tableName = fk_data['tableName'],
        keyName = fk_data['keyName'][0],
        fkTable = fk_data['fkTable'],
        fkCol = fk_data['fkCol'][0],
    )

def debugTap(f):
    def _debugTap(*args, **kwargs):
        dprint('%s(%s)' % (f.__name__, ', '.join(list(map(repr, args)) + ['%s = %s' % (k, repr(v)) for k, v in kwargs.items()])))
        return f(*args, **kwargs)
    return _debugTap

def unquotedString(*args, **kwargs):
    return QuotedString(*args, **kwargs)

def grammar():
    identifier = Word(alphas + '_', alphanums + '_')

    rhs = Word(alphanums + '_')

    tablename_def = ( Word(alphas + "_") | unquotedString("`") )
    colname_def = ( Word(alphas + "_") | unquotedString("`") )
    collist_def = delimitedList(colname_def)

    parenthesis = Forward()
    parenthesis <<= "(" + ZeroOrMore(CharsNotIn("()") | parenthesis) + ")"

    foreign_key_constraint_def = (
        Literal("CONSTRAINT") +
        tablename_def +
        Literal("FOREIGN") +
        Literal("KEY") +
        parens(collist_def).setResultsName('localColumnNames') +
        Literal("REFERENCES") +
        tablename_def.setResultsName('foreignTableName') +
        parens(collist_def).setResultsName('foreignColumnNames')
    )

    foreign_key_constraint_def.setParseAction(foreign_key_constraint_act)

    field_def = OneOrMore(Word(alphanums + "_\"'`:-") | parenthesis)
    field_def.setParseAction(field_act)

    field_list_def = delimitedList(field_def)
    field_list_def.setParseAction(field_list_act)

    key_def = (
        Optional(Literal("UNIQUE") | Literal("PRIMARY")) + Literal("KEY") + ZeroOrMore(CharsNotIn(','))
    )

    table_parts_def = delimitedList(foreign_key_constraint_def | field_def)

    table_option_def = (identifier + Literal('=') + rhs) | identifier
    table_options_def = ZeroOrMore(table_option_def)

    create_table_def = (
        Literal("CREATE TABLE") +
        Optional(Literal("IF NOT EXISTS")) +
        tablename_def.setResultsName("tableName") +
        "(" +
        table_parts_def.setResultsName("table_parts") +
        ")" +
        table_options_def +
        ";"
    )
    create_table_def.setParseAction(create_table_act)

    add_fkey_def = Literal("ALTER") + "TABLE" + "ONLY" + tablename_def.setResultsName("tableName") + "ADD" + "CONSTRAINT" + Word(alphanums + "_") + "FOREIGN" + "KEY" + "(" + Word(alphanums + "_").setResultsName("keyName") + ")" + "REFERENCES" + Word(alphanums + "_").setResultsName("fkTable") + "(" + Word(alphanums + "_").setResultsName("fkCol") + ")" + Optional(Literal("DEFERRABLE")) + ";"
    add_fkey_def.setParseAction(add_fkey_act)

    other_statement_def = OneOrMore(CharsNotIn(";")) + ";"
    other_statement_def.setParseAction(other_statement_act)

    comment_def = "--" + ZeroOrMore(CharsNotIn("\n"))
    comment_def.setParseAction(other_statement_act)

    return OneOrMore(comment_def | create_table_def | add_fkey_def | other_statement_def)


preamble = '''/*
 * Graphviz of '%(filename)s', created %(timestamp)s
 * Generated from https://github.com/rm-hull/sql_graphviz
 */
digraph g {
  graph [
    rankdir="LR",
    scale=false,
    overlap=0,
    splines=polyline,
    concentrate=1,
    pad="0.5",
    nodesep="0.5",
    ranksep="2"
  ];
'''

def graphviz(filename):
    print(preamble % {
        'filename': filename,
        'timestamp': datetime.now()
    })

    for i in grammar().parseFile(filename):
        if i != "":
            print(i)
    print("}")

if __name__ == '__main__':
    filename = sys.stdin if len(sys.argv) == 1 else sys.argv[1]
    graphviz(filename)
