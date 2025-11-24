{
    "name": "Welcome Image",
    "version": "1.0",
    "category": "Tools",
    "summary": "Show a welcome image when login.",
    "author": "Your Name",
    "depends": ["web"],
    "data": [
        "views/welcome_view.xml",
    ],
    "assets": {
            "web.assets_backend": [
                "sonha_dau_trang/static/src/js/welcome_action.js",
            ]
        },
    "installable": True,
    "application": True,
}