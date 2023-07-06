from flask import Flask, render_template, url_for, redirect, session, flash, request
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, ValidationError
from wtforms.validators import DataRequired, Email, EqualTo

# データベース関係のインポート
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from pytz import timezone


app = Flask(__name__)

app.config["SECRET_KEY"] = "mysecretkey"  # ランダム文字列でOK。環境変数として登録することが多い

basedir = os.path.abspath(os.path.dirname(__file__))  # __file__は現在のスクリプトのファイルパスを表す特殊な変数
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    basedir, "data.sqlite"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
Migrate(app, db)

from sqlalchemy.engine import Engine
from sqlalchemy import event


# 外部キー制約の有効化
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class User(db.Model):  # データベースのテーブルを表すために使用される抽象基底クラス
    __tablename__ = "users"  # usersというテーブルネームを指定

    id = db.Column(db.Integer, primary_key=True)  # 主キーとなるカラム
    email = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    administrator = db.Column(db.String(1))
    post = db.relationship(
        "BlogPost", backref="author", lazy="dynamic"
    )  # 1対多のリレーションシップ authorという名前で参照できるようにする。

    def __init__(self, email, username, password_hash, administrator):  # インスタンス時に
        self.email = email
        self.username = username
        self.password_hash = password_hash
        self.administrator = administrator

    def __repr__(self):
        return f"UserName:{self.username}"


class BlogPost(db.Model):
    __tablename__ = "blog_post"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    date = db.Column(db.DateTime, default=datetime.now(timezone("Asia/Tokyo")))
    title = db.Column(db.String(140))
    text = db.Column(db.Text)
    summary = db.Column(db.String(140))
    featured_image = db.Column(db.String(140))

    def __init__(self, title, text, featured_image, user_id, summary):
        self.title = title
        self.text = text
        self.featured_image = featured_image
        self.user_id = user_id
        self.summary = summary

    def __repr__(self):
        return f"PostID:{self.id},Title:{self.title},Author:{self.author} \n"


class RegistrationForm(FlaskForm):
    email = StringField(
        "メールアドレス", validators=[DataRequired(), Email(message="正しいメールアドレスを入力してください")]
    )
    username = StringField("ユーザー名", validators=[DataRequired()])
    password = PasswordField(
        "パスワード",
        validators=[DataRequired(), EqualTo("pass_confirm", message="パスワードが一致していません")],
    )
    pass_confirm = PasswordField("パスワード（確認）", validators=[DataRequired()])
    submit = SubmitField("登録")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("入力されたユーザー名はすでに使われています")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError("入力されたメールアドレスはすでに登録されています")


class UpdateUserForm(FlaskForm):
    email = StringField(
        "メールアドレス", validators=[DataRequired(), Email(message="正しいメールアドレスを入力してください")]
    )
    username = StringField("ユーザー名", validators=[DataRequired()])
    password = PasswordField(
        "パスワード", validators=[EqualTo("pass_confirm", message="パスワードが一致していません")]
    )
    pass_confirm = PasswordField("パスワード（確認）")
    submit = SubmitField("更新")

    def validate_email(self, field):  # validate_on_submit時に実行される
        if (
            User.query.filter(User.id != self.id).filter_by(email=field.data).first()
        ):  # 更新ユーザー以外の同じ名前のデータが有る場合を検索
            raise ValidationError("入力されたメールアドレスはすでに登録されています")

    def validate_username(self, field):
        if User.query.filter(User.id != self.id).filter_by(username=field.data).first():
            raise ValidationError("入力されたユーザー名はすでに登録されています")

    def __init__(self, user_id, *args, **kwargs):
        super(UpdateUserForm, self).__init__(*args, **kwargs)  # initする際に継承したい場合のおまじない
        self.id = user_id


# View関数
# ユーザー登録フォーム


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # session["email"] = form.email.data
        # session["username"] = form.username.data
        # session["password"] = form.password.data
        user = User(
            email=form.email.data,
            username=form.username.data,
            password_hash=form.password.data,
            administrator="0",
        )
        db.session.add(user)
        db.session.commit()
        flash("ユーザーが登録されました")
        return redirect(url_for("user_maintenance"))
    return render_template("register.html", form=form)


# ユーザー管理フォーム
@app.route("/user_maintenance")
def user_maintenance():
    page = request.args.get("page", 1, type=int)
    users = User.query.order_by(User.id).paginate(
        page=page, per_page=10
    )  # idの昇順でデータベースのデータを取得
    return render_template("user_maintenance.html", users=users)


# アカウント更新フォーム
@app.route("/<int:user_id>/account", methods=["GET", "POST"])
def account(user_id):
    user = User.query.get_or_404(user_id)
    form = UpdateUserForm(user_id)
    if form.validate_on_submit():  # valiが合ってたら更新処理をする
        user.username = form.username.data
        user.email = form.email.data
        if form.password.data:
            user.password_hash = form.password.data
        db.session.commit()
        flash("ユーザーアカウントが更新されました")
        return redirect(url_for("user_maintenance"))
    elif request.method == "GET":  # 最初はGETの処理でアカウントデータをフォームに読み込む
        form.username.data = user.username
        form.email.data = user.email

    return render_template("account.html", form=form)


# 削除用のビュー関数
@app.route("/<int:user_id>/delete", methods=["GET", "POST"])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("ユーザーアカウントが削除されました")
    return redirect(url_for("user_maintenance"))


if __name__ == "__main__":
    app.run(debug=True, port=8888)
