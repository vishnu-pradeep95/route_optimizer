"""Abstract interface for data importers.

Why an interface?
Different businesses use different sources: CSV files, Google Sheets,
ERP APIs, etc. By defining a common interface, the optimizer and API
don't care where the data came from — they just get a list of Orders.
"""

from typing import Protocol, runtime_checkable

from core.models.order import Order


@runtime_checkable
class DataImporter(Protocol):
    """Protocol for importing delivery orders from any source.

    Implementations:
    - CsvImporter: reads CSV/Excel exported from CDCMS or any spreadsheet
    - (Future) ApiImporter: pulls from a booking system's REST API
    """

    def import_orders(self, source: str) -> list[Order]:
        """Import orders from a data source.

        Args:
            source: Path to file, URL, or connection string depending
                on the implementation.

        Returns:
            List of Order objects ready for geocoding and optimization.
            Orders may have location=None if addresses need geocoding.

        Raises:
            ImportError: If the source format is invalid or unreadable.
        """
        ...
