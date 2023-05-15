from abc import ABC
import zope.interface

class IProvider(zope.interface.Interface):
    """Unified interface to provide data to the bot"""

    def fetch_data():
        """Gets the required data (substitutions, timetable, etc.) from any required source"""

class SubstitutionsProvider():
    zope.interface.implements(Provider)

    def fetch_data():
        parse_eduhouse()
        return parsed_data

class TimetableProvider():
    zope.interface.implements(Provider)

    def fetch_data():
        get_timetable()
        return timetable

class SystemFacade(ABC):
    substitutionsProvider: IProvider
    timetableProvider: IProvider