import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
def test_create_user_uses_email_and_hashes_password():
    user = User.objects.create_user(
        email="Finance@Example.com",
        password="SecretPass123!",
        first_name="Ada",
    )

    assert user.email == "finance@example.com"
    assert user.USERNAME_FIELD == "email"
    assert user.check_password("SecretPass123!")
    assert user.password != "SecretPass123!"
    assert not user.password.startswith("SecretPass")
    assert user.is_active is True
    assert user.is_staff is False


@pytest.mark.django_db
def test_email_must_be_unique():
    User.objects.create_user(email="same@example.com", password="SecretPass123!")

    with pytest.raises(IntegrityError):
        User.objects.create_user(email="same@example.com", password="OtherPass123!")


@pytest.mark.django_db
def test_user_can_be_deactivated():
    user = User.objects.create_user(email="agent@example.com", password="SecretPass123!")
    assert user.is_active is True

    user.is_active = False
    user.save(update_fields=["is_active"])

    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_create_superuser_flags():
    admin = User.objects.create_superuser(
        email="owner@example.com",
        password="SecretPass123!",
    )
    assert admin.is_staff is True
    assert admin.is_superuser is True
    assert admin.is_active is True
