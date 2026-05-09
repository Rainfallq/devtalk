from fastapi import FastAPI, Depends, Request, Form, HTTPException, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional
import os

from app.database import get_db, init_db, User, Post, Comment, Vote, Tag
from app.auth import hash_password, verify_password, create_token, get_current_user_from_cookie

app = FastAPI(title="DevTalk", description="Community Discussion Platform - MVP Prototype")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.on_event("startup")
def startup():
    init_db()
    _seed_tags()

def _seed_tags():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        if db.query(Tag).count() == 0:
            for name in ["general", "questions", "announcements", "feedback", "offtopic"]:
                db.add(Tag(name=name))
            db.commit()
    finally:
        db.close()

# --- helpers ---

def get_post_score(post_id: int, db: Session) -> int:
    votes = db.query(Vote).filter(Vote.post_id == post_id).all()
    return sum(v.direction for v in votes)

def get_comment_score(comment_id: int, db: Session) -> int:
    votes = db.query(Vote).filter(Vote.comment_id == comment_id).all()
    return sum(v.direction for v in votes)

def require_login(user=Depends(get_current_user_from_cookie)):
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user

# --- routes: pages ---

@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = "", db: Session = Depends(get_db),
          user=Depends(get_current_user_from_cookie)):
    if q.strip():
        posts = db.query(Post).filter(
            or_(Post.title.ilike(f"%{q}%"), Post.body.ilike(f"%{q}%"))
        ).order_by(Post.created_at.desc()).all()
    else:
        posts = db.query(Post).order_by(Post.created_at.desc()).all()
    tags = db.query(Tag).order_by(Tag.name).all()
    post_scores = {str(p.id): get_post_score(p.id, db) for p in posts}
    return templates.TemplateResponse("index.html", {
        "request": request, "posts": posts, "tags": tags,
        "user": user, "q": q, "post_scores": post_scores
    })

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user=Depends(get_current_user_from_cookie)):
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})

@app.post("/register")
def register(request: Request, response: Response,
             username: str = Form(...), password: str = Form(...),
             db: Session = Depends(get_db)):
    username = username.strip()
    if not username or not password:
        return templates.TemplateResponse("register.html",
            {"request": request, "error": "Username and password are required."})
    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse("register.html",
            {"request": request, "error": "Username already taken."})
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.id, user.username, user.role)
    r = RedirectResponse("/", status_code=302)
    r.set_cookie("access_token", token, httponly=True, max_age=86400)
    return r

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user=Depends(get_current_user_from_cookie)):
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
def login(request: Request, response: Response,
          username: str = Form(...), password: str = Form(...),
          db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username.strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html",
            {"request": request, "error": "Invalid username or password."})
    token = create_token(user.id, user.username, user.role)
    r = RedirectResponse("/", status_code=302)
    r.set_cookie("access_token", token, httponly=True, max_age=86400)
    return r

@app.get("/logout")
def logout():
    r = RedirectResponse("/", status_code=302)
    r.delete_cookie("access_token")
    return r

@app.get("/post/new", response_class=HTMLResponse)
def new_post_page(request: Request, db: Session = Depends(get_db),
                  user=Depends(get_current_user_from_cookie)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    tags = db.query(Tag).order_by(Tag.name).all()
    return templates.TemplateResponse("new_post.html", {"request": request, "tags": tags, "user": user, "error": None})

@app.post("/post/new")
def create_post(request: Request, title: str = Form(...), body: str = Form(...),
                tags: list[int] = Form(default=[]), new_tag: str = Form(default=""),
                db: Session = Depends(get_db), user=Depends(get_current_user_from_cookie)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    title = title.strip()
    body = body.strip()
    all_tags = db.query(Tag).order_by(Tag.name).all()
    def err(msg):
        return templates.TemplateResponse("new_post.html",
            {"request": request, "tags": all_tags, "user": user, "error": msg})
    if not title or len(title) > 150:
        return err("Title must be 1-150 characters.")
    if len(body) < 20:
        return err("Body must be at least 20 characters.")
    post = Post(title=title, body=body, author_id=int(user["sub"]))
    db.add(post)
    for tid in tags:
        tag = db.query(Tag).get(tid)
        if tag:
            post.tags.append(tag)
    if new_tag.strip():
        nt = new_tag.strip().lower()
        existing = db.query(Tag).filter(Tag.name == nt).first()
        if not existing:
            existing = Tag(name=nt)
            db.add(existing)
        if existing not in post.tags:
            post.tags.append(existing)
    if not post.tags:
        return err("Select or create at least one tag.")
    db.commit()
    db.refresh(post)
    return RedirectResponse(f"/post/{post.id}", status_code=302)

@app.get("/post/{post_id}", response_class=HTMLResponse)
def view_post(post_id: int, request: Request, db: Session = Depends(get_db),
              user=Depends(get_current_user_from_cookie)):
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    score = get_post_score(post_id, db)
    top_comments = db.query(Comment).filter(
        Comment.post_id == post_id, Comment.parent_id == None
    ).order_by(Comment.created_at).all()
    comment_scores = {}
    for c in top_comments:
        comment_scores[c.id] = get_comment_score(c.id, db)
        for r in c.replies:
            comment_scores[r.id] = get_comment_score(r.id, db)
    user_vote = None
    if user:
        v = db.query(Vote).filter(Vote.user_id == int(user["sub"]), Vote.post_id == post_id).first()
        if v:
            user_vote = v.direction
    return templates.TemplateResponse("post.html", {
        "request": request, "post": post, "user": user,
        "score": score, "top_comments": top_comments,
        "comment_scores": comment_scores, "user_vote": user_vote
    })

@app.post("/post/{post_id}/comment")
def add_comment(post_id: int, body: str = Form(...), parent_id: Optional[int] = Form(default=None),
                db: Session = Depends(get_db), user=Depends(get_current_user_from_cookie)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    if parent_id:
        parent = db.query(Comment).get(parent_id)
        if parent and parent.parent_id is not None:
            return RedirectResponse(f"/post/{post_id}", status_code=302)
    body = body.strip()
    if not body:
        return RedirectResponse(f"/post/{post_id}", status_code=302)
    c = Comment(body=body, post_id=post_id, author_id=int(user["sub"]), parent_id=parent_id)
    db.add(c)
    db.commit()
    return RedirectResponse(f"/post/{post_id}", status_code=302)

@app.get("/tag/{tag_id}", response_class=HTMLResponse)
def tag_view(tag_id: int, request: Request, db: Session = Depends(get_db),
             user=Depends(get_current_user_from_cookie)):
    tag = db.query(Tag).get(tag_id)
    if not tag:
        raise HTTPException(status_code=404)
    posts = [p for p in tag.posts]
    posts.sort(key=lambda p: p.created_at, reverse=True)
    post_scores = {str(p.id): get_post_score(p.id, db) for p in posts}
    return templates.TemplateResponse("tag.html", {
        "request": request, "tag": tag, "posts": posts, "user": user, "post_scores": post_scores
    })

# --- API routes for voting (JSON) ---

@app.post("/api/vote")
def vote(request: Request, data: dict, db: Session = Depends(get_db),
         user=Depends(get_current_user_from_cookie)):
    if not user:
        return JSONResponse({"error": "not logged in"}, status_code=401)
    uid = int(user["sub"])
    direction = int(data.get("direction", 1))
    post_id = data.get("post_id")
    comment_id = data.get("comment_id")

    if post_id:
        post_id = int(post_id)
        post = db.query(Post).get(post_id)
        if not post:
            return JSONResponse({"error": "not found"}, status_code=404)
        if post.author_id == uid:
            return JSONResponse({"error": "cannot vote on own content"}, status_code=400)
        existing = db.query(Vote).filter(Vote.user_id == uid, Vote.post_id == post_id).first()
        if existing:
            if existing.direction == direction:
                db.delete(existing)
            else:
                existing.direction = direction
        else:
            db.add(Vote(user_id=uid, post_id=post_id, direction=direction))
        db.commit()
        return JSONResponse({"score": get_post_score(post_id, db)})

    if comment_id:
        comment_id = int(comment_id)
        comment = db.query(Comment).get(comment_id)
        if not comment:
            return JSONResponse({"error": "not found"}, status_code=404)
        if comment.author_id == uid:
            return JSONResponse({"error": "cannot vote on own content"}, status_code=400)
        existing = db.query(Vote).filter(Vote.user_id == uid, Vote.comment_id == comment_id).first()
        if existing:
            if existing.direction == direction:
                db.delete(existing)
            else:
                existing.direction = direction
        else:
            db.add(Vote(user_id=uid, comment_id=comment_id, direction=direction))
        db.commit()
        return JSONResponse({"score": get_comment_score(comment_id, db)})

    return JSONResponse({"error": "missing target"}, status_code=400)

# --- OpenAPI docs are auto-generated by FastAPI at /docs ---
