#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904

import unittest

from Acquisition import Implicit
from ExtensionClass import Base

from zope.schema.interfaces import SchemaNotProvided
from zope.schema.interfaces import WrongType

from nti.schema.field import Object
from nti.schema.field import ValidTextLine as TextLine

from nti.schema.fieldproperty import AcquisitionFieldProperty
from nti.schema.fieldproperty import AdaptingFieldProperty
from nti.schema.fieldproperty import AdaptingFieldPropertyStoredThroughField
from nti.schema.fieldproperty import UnicodeConvertingFieldProperty
from nti.schema.fieldproperty import createFieldProperties
from nti.schema.fieldproperty import createDirectFieldProperties

from zope import interface

from hamcrest import assert_that
from hamcrest import is_
from hamcrest import has_property
from hamcrest import has_key
from hamcrest import none
from hamcrest import is_not
does_not = is_not
from hamcrest import has_length
from hamcrest import calling
from hamcrest import raises

from nti.testing.matchers import aq_inContextOf


class TestAqFieldProperty(unittest.TestCase):

    def test_aq_property(self):

        class IBaz(interface.Interface):
            pass

        class IFoo(interface.Interface):
            ob = Object(IBaz)

        @interface.implementer(IBaz)
        class Baz(object):
            pass

        class BazAQ(Implicit, Baz):
            pass

        @interface.implementer(IFoo)
        class Foo(Base):
            ob = AcquisitionFieldProperty(IFoo['ob'])

        assert_that(Foo, has_property('ob', is_(AcquisitionFieldProperty)))

        foo = Foo()
        assert_that(foo, has_property('ob', none()))

        foo.ob = Baz()
        assert_that(foo, has_property('ob', is_not(aq_inContextOf(foo))))

        foo.ob = BazAQ()
        assert_that(foo, has_property('ob', aq_inContextOf(foo)))

class TestCreateFieldProperties(unittest.TestCase):

    def test_create_field_properties(self):
        class IBaz(interface.Interface):
            pass

        class IA(interface.Interface):
            a = TextLine(title="a")

        class IB(IA):
            b = Object(IBaz)

        class A(object):
            createFieldProperties(IA)

        class B(object):
            createDirectFieldProperties(IB, adapting=True)

        assert_that(A.__dict__, has_key('a'))
        assert_that(B.__dict__, has_key('b'))
        assert_that(B.__dict__, does_not(has_key('a')))
        assert_that(B.__dict__['b'], is_(AdaptingFieldProperty))

        # And nothing extra crept in, just the four standard things
        # __dict__, __doct__, __module__, __weakref__, and b
        assert_that(B.__dict__, has_length(5))

class TestUnicodeFieldProperty(unittest.TestCase):

    def test_set_bytes(self):
        class IA(interface.Interface):
            a = TextLine(title="a")

        class A(object):
            a = UnicodeConvertingFieldProperty(IA['a'])

        a = A()
        a.a = b'abc'

        assert_that(a, has_property('a', is_(u'abc')))

class TestAdaptingFieldProperty(unittest.TestCase):

    def test_(self):
        class IBaz(interface.Interface):
            pass

        class IFoo(interface.Interface):
            ob = Object(IBaz)

        @interface.implementer(IBaz)
        class Baz(object):
            pass

        class CantConform(object):
            pass

        class Conforms(object):
            def __conform__(self, iface):
                return Baz()

        for fp in AdaptingFieldProperty, AdaptingFieldPropertyStoredThroughField:

            assert_that(calling(fp).with_args(None), raises(WrongType))

            @interface.implementer(IFoo)
            class O(object):
                ob = fp(IFoo['ob'])

            obj = O()

            # First, can't set it
            try:
                obj.ob = CantConform()
                self.fail("Should raise NotProvided")
            except SchemaNotProvided:
                pass

            # But this can be adapted
            obj.ob = Conforms()
            assert_that(obj.ob, is_(Baz))


if __name__ == '__main__':
    unittest.main()