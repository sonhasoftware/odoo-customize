# Part of Odoo. See LICENSE file for full copyright and licensing details.
import psycopg2

from odoo import tools
from odoo.exceptions import UserError
from odoo.tools import SQL

from . import controllers
from . import models
from . import orm
from . import utils
from . import wizard

MISSING_PGVECTOR_LOG_MESSAGE = """\
PostgreSQL extension 'vector' is required to enable RAG for AI agents.
More information at https://github.com/pgvector/pgvector.
"""


def pgvector_is_available(env):
    try:
        with tools.mute_logger('odoo.sql_db'), env.cr.savepoint():
            env.cr.execute(
                SQL("CREATE EXTENSION IF NOT EXISTS vector"))
    except psycopg2.errors.FeatureNotSupported:
        raise UserError(MISSING_PGVECTOR_LOG_MESSAGE)


def _pre_init_ai(env):
    pgvector_is_available(env)
