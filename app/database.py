from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime,
    ForeignKey, Table, UniqueConstraint, Enum, Index
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import os

# Connection string - set DEVTALK_DATABASE_URL env variable or edit below
DATABASE_URL = os.getenv(
    "DEVTALK_DATABASE_URL",
    "postgresql://devtalk_user:devtalk_pass@localhost:5432/devtalk"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

post_tags = Table(
    "post_tags", Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE")),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE")),
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), default="user", nullable=False)  # user | moderator
    created_at = Column(DateTime, default=datetime.utcnow)
    posts = relationship("Post", back_populates="author")
    comments = relationship("Comment", back_populates="author")

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    title = Column(String(150), nullable=False)
    body = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    author = relationship("User", back_populates="posts")
    tags = relationship("Tag", secondary=post_tags, backref="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete")

    # Index on created_at for feed ordering (as per NFR01 in A1)
    __table_args__ = (
        Index("ix_posts_created_at", "created_at"),
    )

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    body = Column(Text, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    author = relationship("User", back_populates="comments")
    post = relationship("Post", back_populates="comments")
    replies = relationship(
        "Comment",
        backref=__import__("sqlalchemy").orm.backref("parent", remote_side="Comment.id")
    )

    __table_args__ = (
        Index("ix_comments_post_id", "post_id"),
    )

class Vote(Base):
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    direction = Column(Integer, nullable=False)  # 1 or -1

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_vote_post"),
        UniqueConstraint("user_id", "comment_id", name="uq_vote_comment"),
        Index("ix_votes_user_id", "user_id"),
    )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)

def seed_tags(db):
    if db.query(Tag).count() == 0:
        for name in ["general", "questions", "announcements", "feedback", "offtopic"]:
            db.add(Tag(name=name))
        db.commit()
