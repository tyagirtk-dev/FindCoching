from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, PasswordField, FloatField, SelectField, TextAreaField, DecimalField
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, NumberRange, Regexp, Optional
)


MOBILE_REGEX = r"^[0-9]{10}$"


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])


class StudentRegistrationForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    mobile = StringField("Mobile Number", validators=[DataRequired(), Regexp(MOBILE_REGEX, message="Enter a valid 10-digit mobile number")])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, message="Password must be at least 8 characters")])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password", message="Passwords must match")])

    address = TextAreaField("Address", validators=[DataRequired(), Length(max=500)])
    state = StringField("State", validators=[DataRequired(), Length(max=120)])
    city = StringField("City", validators=[DataRequired(), Length(max=120)])
    pincode = StringField("Pincode", validators=[DataRequired(), Length(min=4, max=12)])
    latitude = FloatField("Latitude", validators=[DataRequired(), NumberRange(min=-90, max=90)])
    longitude = FloatField("Longitude", validators=[DataRequired(), NumberRange(min=-180, max=180)])

    student_class = StringField("Class", validators=[DataRequired(), Length(max=40)])
    subjects_required = StringField("Subjects Required (comma separated)", validators=[DataRequired(), Length(max=500)])


class TeacherRegistrationForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    mobile = StringField("Mobile Number", validators=[DataRequired(), Regexp(MOBILE_REGEX, message="Enter a valid 10-digit mobile number")])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, message="Password must be at least 8 characters")])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password", message="Passwords must match")])

    photo = FileField("Photo", validators=[FileRequired(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Images only")])
    aadhaar = FileField("Aadhaar / Government ID", validators=[FileRequired(), FileAllowed(["pdf", "png", "jpg", "jpeg"], "PDF or image only")])
    qualification_certificate = FileField("Qualification Certificate", validators=[FileRequired(), FileAllowed(["pdf", "png", "jpg", "jpeg"], "PDF or image only")])

    experience_years = DecimalField("Experience (years)", validators=[DataRequired(), NumberRange(min=0, max=60)])
    subjects = StringField("Subjects (comma separated)", validators=[DataRequired(), Length(max=500)])
    classes = StringField("Classes taught (comma separated)", validators=[DataRequired(), Length(max=255)])
    teaching_mode = SelectField("Teaching Mode", choices=[("online", "Online"), ("offline", "Offline"), ("both", "Both")], validators=[DataRequired()])
    monthly_fees = DecimalField("Monthly Fees", validators=[DataRequired(), NumberRange(min=0)])

    address = TextAreaField("Address", validators=[DataRequired(), Length(max=500)])
    latitude = FloatField("Latitude", validators=[DataRequired(), NumberRange(min=-90, max=90)])
    longitude = FloatField("Longitude", validators=[DataRequired(), NumberRange(min=-180, max=180)])

    upi_id = StringField("UPI ID", validators=[Optional(), Length(max=120)])
    bank_account_holder = StringField("Account Holder Name", validators=[Optional(), Length(max=120)])
    bank_account_number = StringField("Bank Account Number", validators=[Optional(), Length(max=40)])
    bank_ifsc = StringField("IFSC Code", validators=[Optional(), Length(max=20)])
    bank_name = StringField("Bank Name", validators=[Optional(), Length(max=120)])


class OtpVerifyForm(FlaskForm):
    code = StringField("Verification Code", validators=[DataRequired(), Length(min=4, max=10)])


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])


class ResetPasswordForm(FlaskForm):
    code = StringField("OTP Code", validators=[DataRequired(), Length(min=4, max=10)])
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm New Password", validators=[DataRequired(), EqualTo("password")])
