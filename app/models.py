from typing import List, Optional
from pydantic import BaseModel, Field


class ProfileRequest(BaseModel):
    linkedin_url: str = Field(
        ...,
        description="Full LinkedIn profile URL, e.g. https://www.linkedin.com/in/username/",
    )


class Name(BaseModel):
    first: Optional[str] = None
    last: Optional[str] = None
    full: Optional[str] = None


class Experience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class Education(BaseModel):
    school: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class Certification(BaseModel):
    name: Optional[str] = None
    issuing_organization: Optional[str] = None
    issue_date: Optional[str] = None


class Language(BaseModel):
    name: Optional[str] = None
    proficiency: Optional[str] = None


class ProfileResponse(BaseModel):
    input_url: str
    public_identifier: Optional[str] = None
    name: Name
    headline: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None
    about: Optional[str] = None
    profile_picture_url: Optional[str] = None
    background_image_url: Optional[str] = None
    experience: List[Experience] = []
    education: List[Education] = []
    skills: List[str] = []
    certifications: List[Certification] = []
    languages: List[Language] = []
    scraped_at: str
