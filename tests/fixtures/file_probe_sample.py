"""Fixture — mixed top-level, class methods, and nested functions.

Used by end-to-end tests for the file-level probe (qualified names).
Qualified-name table:

    top_level_plain
    top_level_async
    Outer
      .regular_method
      .class_method
      .static_method
      .Inner
        .Inner.deep_method
    Outer.regular_method.helper        (nested function inside a method)
    with_nested
    with_nested.child
    with_nested.child.grandchild       (double-nested)
"""


def top_level_plain(x, y):
    return x + y


async def top_level_async():
    return 42


class Outer:
    attribute = "I am not a function"

    def regular_method(self, a, b, c, d, e, f):  # 6 params — trips too-many-params
        def helper(z):  # nested function inside a method
            return z * 2

        return helper(a + b + c + d + e + f)

    @classmethod
    def class_method(cls, a):
        return cls, a

    @staticmethod
    def static_method():
        return "static"

    class Inner:
        def deep_method(self):
            return "deep"


def with_nested():
    def child():
        def grandchild():
            return 1

        return grandchild()

    return child()
