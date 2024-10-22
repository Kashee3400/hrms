class LeaveListViewMixin:
    @staticmethod
    def get_headers():
        return [
            {
                "name": "id",
                "title": "ID",
                "size": 50,
                "sortable": True,
                "sortDir": "asc",
            },
            {
                "name": "applied_by",
                "title": "Applied by",
                "size": 50,
                "sortable": True,
                "sortDir": "asc",
            },
            {
                "name": "from_place",
                "title": "Boarding",
                "sortable": True,
                "sortDir": "asc",
            },
            {
                "name": "start_date",
                "title": "Start Date",
                "sortable": True,
                "size": 150,
                "format": "date",
                "sortDir": "asc",
                "formatMask": "dd-mm-yyyy"
            },
            {
                "name": "to_place",
                "title": "Destination",
                "sortable": True,
                "sortDir": "asc",
                "size": 150,
            },
            {
                "name": "end_date",
                "title": "End Date",
                "sortable": True,
                "size": 150,
                "sortDir": "asc",
                "format": "date",
                "formatMask": "dd-mm-yyyy"
            },
            {
                "name": "end_type",
                "title": "End Type",
                "sortable": True,
                "sortDir": "asc",
                "size": 150,
            },
            {
                "name": "days",
                "title": "Days",
                "sortable": True,
                "sortDir": "asc",
                "size": 80
            },
            {
                "name": "status",
                "title": "Status",
                "sortable": True,
                "size": 150,
                "sortDir": "asc",
                "show": True
            }
        ]
