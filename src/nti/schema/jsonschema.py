#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
For producing a JSON schema appropriate for use by clients, based on a Zope schema.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.schema import interfaces as sch_interfaces
from zope.schema import vocabulary as sch_vocabulary

from nti.schema.interfaces import find_most_derived_interface

#: Don't display this by default in the UI
TAG_HIDDEN_IN_UI = "nti.dataserver.users.field_hidden_in_ui"

#: Qualifying details about how the field should be treated, such as data source
TAG_UI_TYPE = 'nti.dataserver.users.field_type'

#: Overrides the value from the field itself
TAG_REQUIRED_IN_UI = 'nti.dataserver.users.field_required'

#: Overrides the value from the field itself, if true
TAG_READONLY_IN_UI = 'nti.dataserver.users.field_readonly'

# Known types
UI_TYPE_EMAIL = 'nti.dataserver.users.interfaces.EmailAddress'
UI_TYPE_HASHED_EMAIL = UI_TYPE_EMAIL + ":Hashed"  # So that a begins-with test will match either, making validation easier

#: Something that can be set once, typically during account creation
UI_TYPE_ONE_TIME_CHOICE = 'nti.dataserver.users.interfaces.OneTimeChoice'

def interface_to_ui_type(iface):
	ui_type = iface.getName()
	ui_type = ui_type[1:] if ui_type.startswith('I') else ui_type
	return ui_type

def ui_type_from_field_iface(field):
	derived_field_iface = find_most_derived_interface(field, sch_interfaces.IField)
	if derived_field_iface is not sch_interfaces.IField:
		ui_type = interface_to_ui_type(derived_field_iface)
		return ui_type
	return None
ui_type_from_field_iface = ui_type_from_field_iface # BWC

def ui_type_from_field(field):
	ui_type = ui_base_type = None
	_type = getattr(field, '_type', None)
	if isinstance(_type, type):
		ui_type = _type.__name__
	elif isinstance(_type, tuple):
		# Most commonly lists subclasses. Most commonly lists subclasses of strings
		if all((issubclass(x, basestring) for x in _type)):
			ui_type = 'basestring'
	else:
		ui_type = ui_type_from_field_iface(field)

	if ui_type in ('unicode', 'str', 'basestring'):
		# These are all 'string' type

		# Can we be more specific?
		ui_type = ui_type_from_field_iface(field)
		if ui_type and ui_type not in ('TextLine', 'Text'):  # Yes we can
			ui_base_type = 'string'
		else:
			ui_type = 'string'
			ui_base_type = 'string'

	return ui_type, ui_base_type
_ui_type_from_field = ui_type_from_field # BWC

class JsonSchemafier(object):

	def __init__(self, schema, readonly_override=None):
		"""
		Create a new schemafier.

		:param schema: The zope schema to use.
		:param bool readonly_override: If given, a boolean value that will replace all
			readonly values in the schema.
		"""
		self.schema = schema
		self.readonly_override = readonly_override

	def _iter_names_and_descriptions(self):
		"""
		Return an iterable across the names and descriptions of the schema.

		Subclass hook to change what is considered.
		"""
		return self.schema.namesAndDescriptions(all=True)

	def allow_field(self, name, field):
		"""
		Return if the field is allowed in the external schema
		"""
		if field.queryTaggedValue(TAG_HIDDEN_IN_UI) or name.startswith('_'):
			return False
		return True

	def ui_types_from_field(self, field):
		"""
		Return the type and base type for the specified field
		"""
		return ui_type_from_field(field)

	def make_schema(self):
		"""
		Create the JSON schema.

		:return: A dictionary consisting of dictionaries, one for each field. All the keys
			are strings and the values are strings, bools, numbers, or lists of primitives.
			Will be suitable for writing to JSON.
		"""
		readonly_override = self.readonly_override

		ext_schema = {}
		for k, v in self._iter_names_and_descriptions():
			__traceback_info__ = k, v
			if interface.interfaces.IMethod.providedBy(v):
				continue
			# v could be a schema field or an interface.Attribute
			if not self.allow_field(k, v):
				continue

			required = getattr(v, 'required', None)
			required = v.queryTaggedValue(TAG_REQUIRED_IN_UI) or required

			if readonly_override is not None:
				readonly = readonly_override
			else:
				readonly = getattr(v, 'readonly', False)
				readonly = v.queryTaggedValue(TAG_READONLY_IN_UI) or readonly

			item_schema = {'name': k,
						   'required': required,
						   'readonly': readonly,
						   'min_length': getattr(v, 'min_length', None),
						   'max_length': getattr(v, 'max_length', None) }
			ui_type = v.queryTaggedValue(TAG_UI_TYPE)
			ui_base_type = None
			if not ui_type:
				ui_type, ui_base_type = self.ui_types_from_field(v)
			else:
				_, ui_base_type = self.ui_types_from_field(v)

			item_schema['type'] = ui_type
			item_schema['base_type'] = ui_base_type

			if sch_interfaces.IChoice.providedBy(v):
				# Vocabulary could be a name or the vocabulary itself
				item_schema['choices'] = ()
				vocabulary = None
				if sch_interfaces.IVocabulary.providedBy(v.vocabulary):
					vocabulary = v.vocabulary
				elif isinstance(v.vocabularyName, basestring):
					name = v.vocabularyName
					vocabulary = sch_vocabulary.getVocabularyRegistry().get(None, name)

				if vocabulary is not None:
					choices = []
					tokens = []
					for term in vocabulary:
						# For BWC, we do different things depending on whether
						# there is a title or not
						if getattr(term, 'title', None):
							try:
								# like nti.externalization, but without the dependency
								choice = term.toExternalObject()
							except AttributeError:
								choice = {'token': term.token,
										  'value': term.value,
										  'title': term.title}

							choices.append(choice)
						else:
							choices.append(term.token)  # bare; ideally this would go away
						tokens.append(term.token)
					item_schema['choices'] = choices
					# common case, these will all be the same type
					if 		not item_schema.get('base_type') \
						and all((isinstance(x, basestring) for x in tokens)):
						item_schema['base_type'] = 'string'

			ext_schema[k] = item_schema

		return ext_schema
