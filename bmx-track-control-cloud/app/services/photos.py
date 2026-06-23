from sqlalchemy.orm import Session

from app.models import Alert, Photo
from app.services.storage import delete_stored_photo


def delete_all_photos(db: Session) -> int:
    photos = db.query(Photo).all()
    deleted_count = len(photos)

    for photo in photos:
        delete_stored_photo(photo.image_url)

    db.query(Photo).delete(synchronize_session=False)
    db.query(Alert).filter(Alert.resolved.is_(False)).update(
        {Alert.resolved: True},
        synchronize_session=False,
    )
    db.commit()
    return deleted_count
