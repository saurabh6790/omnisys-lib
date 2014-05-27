# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import webnotes
import os
from webnotes.utils import get_base_path
from install_erpnext import exec_in_shell, create_user, parse_args
import os, string, random, re

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

	def on_update(self):
		if not (os.path.exists(os.path.join(get_base_path(), "sites"))):
			self.make_primary_sites_settings()
			
		if not (os.path.exists(os.path.join(get_base_path(), "sites", self.doc.site_name))):
			self.create_new_site()

	def make_primary_sites_settings(self):
		exec_in_shell("""mkdir {path}/sites """.format(path=get_base_path()))

		with open(os.path.join(get_base_path(), "conf.py"), "a") as conf_file:
			conf_file.write('\nsites_dir = "%s"' % ("{path}/sites".format(path=get_base_path())))


		exec_in_shell(""" mkdir -p {path}/sites/{site_name}/
			""".format(path=get_base_path(), site_name= self.doc.site_name))

		exec_in_shell(""" mv {path}/public {path}/sites/{site_name}/public
			""".format(path=get_base_path(), site_name= self.doc.site_name))
		

		with open("conf.py") as temp:
			lines = temp.readlines()
		
		db_name = lines[7][:-1].split('=')
		db_name = '"'+ db_name[0] + '" :'+ db_name[1].replace("'", '"') 
		
		db_password = lines[8][:-1].split('=')
		db_password = '"'+ db_password[0] + '" :'+ db_password[1].replace("'", '"')

		with open(os.path.join(get_base_path(), "site_config.json"), "w") as conf_file:
			conf_file.write("{\n"+db_name+",\n"+db_password+"\n}")	

		exec_in_shell(""" mv {path}/site_config.json {path}/sites/{site_name}/
			""".format(path=get_base_path(), site_name= self.doc.site_name))


		exec_in_shell(""" ./lib/wnf.py --build """)
		self.add_to_hosts()
		# self.update_nginx_conf()

	def create_new_site(self):

		root_password = webnotes.conn.get_value("Global Defaults", None, "mysql_root_password")

		exec_in_shell("""{path}/lib/wnf.py --install {dbname} --root-password {root_password} --site {name}
			""".format(path=get_base_path(), dbname=self.doc.site_name.replace('.', '_'), root_password=root_password, name=self.doc.site_name))

		self.add_to_hosts()

		exec_in_shell("{path}/lib/wnf.py --build".format(path=get_base_path()))

		self.update_db_name_pwd()

	def add_to_hosts(self):
		# webnotes.errprint("host")
		with open('/etc/hosts', 'rt') as f:
			s = f.read() + '\n' + '127.0.0.1\t\t\t %s \n'%self.doc.site_name
			with open('hosts', 'wt') as outf:
				outf.write(s)

		root_password = webnotes.conn.get_value("Global Defaults", None, "server_root_password")

		os.system('echo {server_root_password} | sudo -S mv {path}/hosts /etc/hosts'.format(server_root_password=root_password, path=get_base_path()))

	def update_db_name_pwd(self):
		os.path.join(get_base_path(), "sites", self.doc.site_name, 'site_config.json')
		with open (os.path.join(get_base_path(), "sites", self.doc.site_name, 'site_config.json'), 'r') as site_config:
			lines = site_config.readlines()

		db_name = lines[1].split(':')[1].replace('"','')[:-3]
		db_pwd = lines[2].split(':')[1].replace('"','')[:-1]
		webnotes.conn.sql("update `tabSite Details` set database_name = LTRIM('%s'), database_password = LTRIM('%s') where name = '%s' "%(db_name, db_pwd, self.doc.name))
		webnotes.conn.sql("commit")

	def update_global_defaults(self):
		site_details = webnotes.conn.sql("select database_name, database_password from `tabSite Details` where name = '%s'"%(self.doc.name))
		if site_details:
			import MySQLdb
			myDB = MySQLdb.connect(user="%s"%site_details[0][0], passwd="%s"%site_details[0][1], db="%s"%site_details[0][0])
			cHandler = myDB.cursor()
			cHandler.execute("update  tabSingles set value = '%s' where field='is_active' and doctype = 'Global Defaults'"%self.doc.is_active)
			cHandler.execute("commit")

@webnotes.whitelist(allow_guest=True)
def get_installation_note(site_name ,_type='POST'):
	#from webnotes.model.doc import Document
	
	site_name = get_site_name(site_name)
	import webnotes
	# return "hi"
	site = webnotes.bean({
			"doctype":"Site Details",
			"site_name": site_name,
			"is_active":"1"
		}).insert()
	webnotes.conn.sql("commit")
	if site:
		return {"status":"200"}
	# http://saurabh.erp.com:8000/server.py?cmd=core.doctype.site_details.site_details.get_installation_note&site_name=rohit3.erp.com&_type='POST'
def get_site_name(site_name):
	if len(site_name)>16:
		site_name= site_name[:16]
		#webnotes.errprint(site_name)

	else:
		site_name=site_name
		#webnotes.errprint(site_name)
	return site_name
@webnotes.whitelist(allow_guest=True)
def activate_deactivate(site_name , is_active, _type='POST'):
	# return "hi"
	from webnotes.model.doc import Document
	from webnotes.utils import now
	site_name = get_site_name(site_name)
	site_details = webnotes.conn.sql("select database_name, database_password from `tabSite Details` where name = '%s'"%(site_name))
	#return site_details
	if site_details:
		import MySQLdb
		try:
			myDB = MySQLdb.connect(user="%s"%site_details[0][0], passwd="%s"%site_details[0][1], db="%s"%site_details[0][0])
			cHandler = myDB.cursor()
			cHandler.execute("update  tabSingles set value = '%s' where field='is_active' and doctype = 'Global Defaults'"%is_active)
			cHandler.execute("commit")
			myDB.close()

			d = Document("Site Log")
			d.site_name =site_name
			d.purpose = 'Activation/Deactivation'
			d.is_active = is_active
			d.date_time = now()
			d.save()
			webnotes.conn.sql("commit")
			return {"status":"200", 'name':d.name}

		except Exception as inst: 
			return {"status":"417", "error":inst}
	else:
		return{"status":"404", "Error":"Site Not Fount"}

@webnotes.whitelist(allow_guest=True)
def update_user_limit(site_name , max_users, _type='POST'):
	from webnotes.model.doc import Document
	from webnotes.utils import now
	site_name = get_site_name(site_name)
	site_details = webnotes.conn.sql("select database_name, database_password from `tabSite Details` where name = '%s'"%(site_name))
	# return site_details
	if site_details:
		import MySQLdb
		try:
			myDB = MySQLdb.connect(user="%s"%site_details[0][0], passwd="%s"%site_details[0][1], db="%s"%site_details[0][0])
			cHandler = myDB.cursor()
			cHandler.execute("update  tabSingles set value = '%s' where field='max_users' and doctype = 'Global Defaults'"%max_users)
			cHandler.execute("commit")
			myDB.close()

			d = Document("Site Log")
			d.site_name =site_name
			d.date_time = now()
			d.purpose = 'Max User Setting'
			d.max_users = max_users
			d.save()
			webnotes.conn.sql("commit")
			return {"status":"200", 'name':d.name}

		except Exception as inst: 
			return {"status":"417", "error":inst}

@webnotes.whitelist(allow_guest=True)
def terminate_tenant(site_name):
	site_name = get_site_name(site_name)
	#return site_name
	delete_db_and_user(site_name)
	delete_site_folder(site_name)
	delete_master_record(site_name)
	return {"status":"200"}

def delete_db_and_user(site_name):
	root_password = webnotes.conn.get_value("Global Defaults", None, "mysql_root_password")
	exec_in_shell("mysql -u root -p'{root_password}' -e'drop database {dbname}'".format(dbname=site_name.replace('.', '_'), root_password=root_password))

	exec_in_shell("mysql -u root -p'{root_password}' -e'drop user {dbname}@localhost'".format(dbname=site_name.replace('.', '_'), root_password=root_password))

def delete_site_folder(site_name):
	exec_in_shell("""rm -r {path}/sites/{site_name} """.format(site_name=site_name, path=get_base_path()))

def delete_master_record(site_name):
	if webnotes.conn.get_value("Site Details", site_name, 'name'):
		webnotes.conn.sql("delete from `tabSite Details` where name = '%s'"%(site_name))
		webnotes.conn.sql("commit")