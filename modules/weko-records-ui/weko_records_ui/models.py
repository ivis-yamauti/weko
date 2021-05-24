# -*- coding: utf-8 -*-
#
# This file is part of WEKO3.
# Copyright (C) 2017 National Institute of Informatics.
#
# WEKO3 is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# WEKO3 is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with WEKO3; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.


"""Database models for weko-admin."""

from datetime import datetime

from flask import current_app
from invenio_db import db
from sqlalchemy import desc, or_
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils.models import Timestamp
from sqlalchemy_utils.types import JSONType

""" PDF cover page model"""


class PDFCoverPageSettings(db.Model):
    """PDF Cover Page Settings."""

    __tablename__ = 'pdfcoverpage_set'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    avail = db.Column(db.Text, nullable=True, default='disable')
    """ PDF Cover Page Availability """

    header_display_type = db.Column(db.Text, nullable=True, default='string')
    """ Header Display('string' or 'image')"""

    header_output_string = db.Column(db.Text, nullable=True, default='')
    """ Header Output String"""

    header_output_image = db.Column(db.Text, nullable=True, default='')
    """ Header Output Image"""

    header_display_position = db.Column(
        db.Text, nullable=True, default='center')
    """ Header Display Position """

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    """ Created Date"""

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now)
    """ Updated Date """

    def __init__(
            self,
            avail,
            header_display_type,
            header_output_string,
            header_output_image,
            header_display_position):
        """Init."""
        self.avail = avail
        self.header_display_type = header_display_type
        self.header_output_string = header_output_string
        self.header_output_image = header_output_image
        self.header_display_position = header_display_position

    @classmethod
    def find(cls, id):
        """Find record by ID."""
        record = db.session.query(cls).filter_by(id=id).first()
        return record

    @classmethod
    def update(
            cls,
            id,
            avail,
            header_display_type,
            header_output_string,
            header_output_image,
            header_display_position):
        """Update."""
        settings = PDFCoverPageSettings(
            avail,
            header_display_type,
            header_output_string,
            header_output_image,
            header_display_position)

        """ update record by ID """
        record = db.session.query(cls).filter_by(id=id).first()

        record.avail = settings.avail
        record.header_display_type = settings.header_display_type
        record.header_output_string = settings.header_output_string
        record.header_output_image = settings.header_output_image
        record.header_display_position = settings.header_display_position
        db.session.commit()
        return record


""" Record UI models """


class InstitutionName(db.Model):
    """Institution Name model."""

    id = db.Column(db.Integer, primary_key=True)
    """Identifier."""

    institution_name = db.Column(db.String(255), default='')
    """Institution name."""

    def __init__(self, name):
        """Constructor."""
        self.institution_name = name

    @classmethod
    def get_institution_name(cls):
        """Get institution name.

        Returns:
            str: institution name

        """
        institution = cls.query.first()
        if institution:
            return institution.institution_name
        return ""

    @classmethod
    def set_institution_name(cls, new_name):
        """Save institution name.

        Args:
            new_name (str): new institution name.

        """
        try:
            with db.session.begin_nested():
                cfg = cls.query.first()
                if cfg:
                    cfg.institution_name = new_name
                    db.session.merge(cfg)
                else:
                    db.session.add(cls(new_name))
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            current_app.logger.error(ex)


class FilePermission(db.Model):
    """File download permission."""

    __tablename__ = 'file_permission'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    """Id."""

    user_id = db.Column(db.Integer, nullable=False)
    """User Id."""

    record_id = db.Column(db.String(255), nullable=False)
    """Record id."""

    file_name = db.Column(db.String(255), nullable=False)
    """File name."""

    usage_application_activity_id = db.Column(db.String(255), nullable=False)
    """Usage Application Activity id."""

    usage_report_activity_id = db.Column(db.String(255), nullable=True)
    """Usage Report Activity id."""

    status = db.Column(db.Integer, nullable=False)
    """Status of the permission."""
    """-1 : Initialized, 0 : Processing, 1: Approved."""

    open_date = db.Column(db.DateTime, nullable=False, default=datetime.now())

    def __init__(self, user_id, record_id, file_name,
                 usage_application_activity_id,
                 usage_report_activity_id, status):
        """Init."""
        self.user_id = user_id
        self.record_id = record_id
        self.file_name = file_name
        self.usage_application_activity_id = usage_application_activity_id
        self.usage_report_activity_id = usage_report_activity_id
        self.status = status

    @classmethod
    def find(cls, user_id, record_id, file_name):
        """Find user 's permission by user_id, record_id, file_name."""
        permission = db.session.query(cls).filter_by(user_id=user_id,
                                                     record_id=record_id,
                                                     file_name=file_name)\
            .first()
        return permission

    @classmethod
    def find_list_permission_by_date(cls, user_id, record_id, file_name,
                                     duration):
        """Find user 's permission by date."""
        list_permission = db.session.query(cls) \
            .filter(
            or_(
                cls.open_date >= duration,
                cls.open_date.is_(None),
            )
        ) \
            .filter_by(user_id=user_id,
                       record_id=record_id,
                       file_name=file_name).order_by(
            desc(cls.id)).all()
        return list_permission

    @classmethod
    def init_file_permission(cls, user_id, record_id, file_name, activity_id):
        """Init a file permission with status = Doing."""
        status_initialized = -1
        file_permission = FilePermission(user_id, record_id, file_name,
                                         activity_id, None,
                                         status_initialized
                                         )
        db.session.add(file_permission)
        db.session.commit()
        return cls

    @classmethod
    def update_status(cls, permission, status):
        """Update a permission 's status."""
        permission.status = status
        db.session.merge(permission)
        db.session.commit()
        return permission

    @classmethod
    def update_open_date(cls, permission, open_date):
        """Update a permission 's open date."""
        permission.open_date = open_date
        db.session.merge(permission)
        db.session.commit()
        return permission

    @classmethod
    def find_by_activity(cls, activity_id):
        """Find user 's permission activity id."""
        permission = db.session.query(cls).filter_by(
            usage_application_activity_id=activity_id) \
            .first()
        return permission

    @classmethod
    def update_usage_report_activity_id(cls, permission, activity_id):
        """Update a permission 's usage report."""
        permission.usage_report_activity_id = activity_id
        db.session.merge(permission)
        db.session.commit()
        return permission

    @classmethod
    def delete_object(cls, permission):
        """Delete permission object.

        @rtype: object
        """
        db.session.delete(permission)
        db.session.commit()


class FileOnetimeDownload(db.Model, Timestamp):
    """File onetime download."""

    __tablename__ = 'file_onetime_download'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    """Identifier"""

    file_name = db.Column(db.String(255), nullable=False)
    """File name"""

    user_mail = db.Column(db.String(255), nullable=False)
    """User mail"""

    record_id = db.Column(db.String(255), nullable=False)
    """Record identifier."""

    download_count = db.Column(db.Integer, nullable=False, default=0)
    """Download count"""

    expiration_date = db.Column(db.Integer, nullable=False, default=0)
    """Expiration Date"""

    extra_info = db.Column(
        db.JSON().with_variant(
            postgresql.JSONB(none_as_null=True),
            'postgresql',
        ).with_variant(
            JSONType(),
            'sqlite',
        ).with_variant(
            JSONType(),
            'mysql',
        ),
        default=lambda: dict(),
        nullable=True
    )
    """Extra info."""

    def __init__(self, file_name, user_mail, record_id, download_count=0,
                 expiration_date=0, extra_info=None):
        """Init.

        :param file_name: File name
        :param user_mail: User mail
        :param record_id: Record identifier
        :param download_count: Download count
        :param expiration_date: Expiration date
        :param extra_info: Extra info want to store
        """
        self.file_name = file_name
        self.user_mail = user_mail
        self.record_id = record_id
        self.download_count = download_count
        self.expiration_date = expiration_date
        self.extra_info = extra_info

    @classmethod
    def create(cls, **data):
        """Create data."""
        try:
            file_download = cls(**data)
            db.session.add(file_download)
            db.session.commit()
            return file_download
        except Exception as ex:
            db.session.rollback()
            current_app.logger.error(ex)
            return None

    @classmethod
    def update_download(cls, **data):
        """Update download count.

        :param data:
        :return:
        """
        try:
            file_name = data.get("file_name")
            user_mail = data.get("user_mail")
            record_id = data.get("record_id")
            file_permission = cls.find(file_name=file_name, user_mail=user_mail,
                                       record_id=record_id)
            if file_permission and len(file_permission) > 0:
                for file in file_permission:
                    if data.get("download_count") is not None:
                        file.download_count = data.get("download_count")
                    if data.get("expiration_date") is not None:
                        file.expiration_date = data.get("expiration_date")
                    if data.get("extra_info"):
                        file.extra_info = data.get("extra_info")
                    db.session.merge(file)
                db.session.commit()
                return file_permission
            return None
        except Exception as ex:
            db.session.rollback()
            current_app.logger.error(ex)
            return None

    @classmethod
    def find(cls, **obj) -> list:
        """Find file onetime download.

        :param obj:
        :return:
        """
        query = db.session.query(cls).filter(
            cls.file_name == obj.get("file_name"),
            cls.record_id == obj.get("record_id"),
            cls.user_mail == obj.get("user_mail"),
        )
        return query.order_by(desc(cls.id)).all()


__all__ = ('PDFCoverPageSettings', 'FilePermission', 'FileOnetimeDownload')
