"""
Serializers for the contacts app.
"""

from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import Company, Contact, ContactNote, ContactTag


class ContactTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactTag
        fields = ["id", "name", "color", "created_at"]
        read_only_fields = ["id", "created_at"]


class ContactNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)

    class Meta:
        model = ContactNote
        fields = [
            "id",
            "contact",
            "content",
            "is_pinned",
            "author",
            "author_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "author", "created_at", "updated_at"]


class CompanyListSerializer(serializers.ModelSerializer):
    contact_count = serializers.ReadOnlyField()
    deal_count = serializers.ReadOnlyField()
    owner_name = serializers.CharField(source="owner.get_full_name", read_only=True, default=None)

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "website",
            "industry",
            "size",
            "phone",
            "email",
            "city",
            "country",
            "owner",
            "owner_name",
            "contact_count",
            "deal_count",
            "created_at",
        ]


class CompanyDetailSerializer(serializers.ModelSerializer):
    contact_count = serializers.ReadOnlyField()
    deal_count = serializers.ReadOnlyField()
    total_deal_value = serializers.ReadOnlyField()
    owner_name = serializers.CharField(source="owner.get_full_name", read_only=True, default=None)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "website",
            "industry",
            "size",
            "annual_revenue",
            "phone",
            "email",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "description",
            "logo",
            "owner",
            "owner_name",
            "created_by",
            "created_by_name",
            "contact_count",
            "deal_count",
            "total_deal_value",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class ContactListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True, default=None)
    owner_name = serializers.CharField(source="owner.get_full_name", read_only=True, default=None)
    full_name = serializers.ReadOnlyField()
    tags = ContactTagSerializer(many=True, read_only=True)

    class Meta:
        model = Contact
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "job_title",
            "company",
            "company_name",
            "status",
            "source",
            "lead_score",
            "owner",
            "owner_name",
            "tags",
            "last_contacted",
            "created_at",
        ]


class ContactDetailSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True, default=None)
    owner_name = serializers.CharField(source="owner.get_full_name", read_only=True, default=None)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=None
    )
    full_name = serializers.ReadOnlyField()
    tags = ContactTagSerializer(many=True, read_only=True)
    notes = ContactNoteSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ContactTag.objects.all(),
        source="tags",
        write_only=True,
        required=False,
    )

    class Meta:
        model = Contact
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "mobile",
            "job_title",
            "department",
            "company",
            "company_name",
            "status",
            "source",
            "lead_score",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "description",
            "avatar",
            "linkedin_url",
            "twitter_handle",
            "tags",
            "tag_ids",
            "owner",
            "owner_name",
            "created_by",
            "created_by_name",
            "notes",
            "last_contacted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "lead_score", "created_at", "updated_at"]


class ContactCreateUpdateSerializer(serializers.ModelSerializer):
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ContactTag.objects.all(),
        source="tags",
        required=False,
    )

    class Meta:
        model = Contact
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "mobile",
            "job_title",
            "department",
            "company",
            "status",
            "source",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "description",
            "avatar",
            "linkedin_url",
            "twitter_handle",
            "tag_ids",
            "owner",
        ]

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        contact = Contact.objects.create(**validated_data)
        if tags:
            contact.tags.set(tags)
        return contact

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        return instance
