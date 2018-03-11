# -*- coding: utf-8 -*-

def create_tables(args):
    sql = ['DROP database if EXISTS awesome;\nCREATE database awesome;'
           '\nuse awesome;'
           '\nGRANT SELECT, INSERT, UPDATE, DELETE on awesome. to "root"@"localhost" identified BY "password";\n']
    for clz in args:
        table_name = clz.table
        sql.append('CREATE TABLE {} ('.format(table_name))
        fields = clz.mappings
        primary_key = None
        for k, v in fields.items():
            sql.append('`{}` {} NOT NULL,'.format(k, v.column_type))
            if v.primary_key:
                primary_key = k
        if primary_key:
            sql.append('primary key({})) engine=innodb default charset=utf8;\n'.format(primary_key))
    with open('schema.sql', 'w', encoding='utf8') as f:
        f.write(' '.join(sql))