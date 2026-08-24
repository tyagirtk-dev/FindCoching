from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, TextAreaField, SelectField, DecimalField, DateField, IntegerField
)
from wtforms.validators import DataRequired, Length, Optional, NumberRange


class HireRequestForm(FlaskForm):
    message = TextAreaField("Message to Teacher", validators=[Optional(), Length(max=1000)])


class HireRespondForm(FlaskForm):
    pass


class AttendanceForm(FlaskForm):
    student_id = SelectField("Student", coerce=int, validators=[DataRequired()])
    date = DateField("Date", validators=[DataRequired()])
    status = SelectField("Status", choices=[("present", "Present"), ("absent", "Absent"), ("leave", "Leave")], validators=[DataRequired()])
    remarks = StringField("Remarks", validators=[Optional(), Length(max=500)])


class PaymentSubmitForm(FlaskForm):
    teacher_id = SelectField("Teacher", coerce=int, validators=[DataRequired()])
    amount = DecimalField("Amount Paid", validators=[DataRequired(), NumberRange(min=1)])
    transaction_id = StringField("Transaction ID", validators=[DataRequired(), Length(max=120)])
    proof_screenshot = FileField("Payment Screenshot", validators=[FileRequired(), FileAllowed(["png", "jpg", "jpeg"], "Images only")])
    billing_period = StringField("Billing Period (e.g. 2026-07)", validators=[Optional(), Length(max=20)])


class PaymentSettingsForm(FlaskForm):
    upi_enabled = SelectField("Enable UPI Payment", choices=[("1", "Enabled"), ("0", "Disabled")], validators=[DataRequired()])
    gpay_upi_id = StringField("Google Pay UPI ID", validators=[Optional(), Length(max=120)])
    phonepe_upi_id = StringField("PhonePe UPI ID", validators=[Optional(), Length(max=120)])
    paytm_upi_id = StringField("Paytm UPI ID", validators=[Optional(), Length(max=120)])
    primary_upi_id = StringField("Primary UPI ID", validators=[DataRequired(), Length(max=120)])
    merchant_name = StringField("Merchant Name", validators=[DataRequired(), Length(max=150)])
    merchant_mobile = StringField("Merchant Mobile Number", validators=[Optional(), Length(max=20)])
    qr_code = FileField("QR Code Upload", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg"], "Images only")])
    payment_instructions = TextAreaField("Payment Instructions", validators=[Optional(), Length(max=2000)])
    min_withdrawal = DecimalField("Minimum Withdrawal", validators=[DataRequired(), NumberRange(min=0)])
    max_withdrawal = DecimalField("Maximum Withdrawal", validators=[DataRequired(), NumberRange(min=0)])
    commission_percent = DecimalField("Commission Percentage", validators=[DataRequired(), NumberRange(min=0, max=100)])
    auto_approval = SelectField("Auto Approval", choices=[("0", "OFF"), ("1", "ON")], validators=[DataRequired()])
    payment_timeout = IntegerField("Payment Timeout (minutes)", validators=[DataRequired(), NumberRange(min=1)])
    maintenance_mode = SelectField("Maintenance Mode", choices=[("0", "OFF"), ("1", "ON")], validators=[DataRequired()])


class WithdrawalRequestForm(FlaskForm):
    amount = DecimalField("Withdrawal Amount", validators=[DataRequired(), NumberRange(min=1)])
    payout_method = SelectField("Payout Method", choices=[("upi", "UPI"), ("bank", "Bank Transfer")], validators=[DataRequired()])


class ReviewForm(FlaskForm):
    rating = IntegerField("Rating (1-5)", validators=[DataRequired(), NumberRange(min=1, max=5)])
    comment = TextAreaField("Comment", validators=[Optional(), Length(max=1000)])


class ComplaintForm(FlaskForm):
    teacher_id = SelectField("Related Teacher (optional)", coerce=int, validators=[Optional()])
    subject = StringField("Subject", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(max=3000)])


class AnnouncementForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    body = TextAreaField("Body", validators=[DataRequired(), Length(max=3000)])
    audience = SelectField("Audience", choices=[("all", "Everyone"), ("teachers", "Teachers Only"), ("students", "Students Only")], validators=[DataRequired()])


class WebsiteSettingsForm(FlaskForm):
    site_name = StringField("Site Name", validators=[DataRequired(), Length(max=120)])
    upi_payee_id = StringField("UPI Payee ID", validators=[Optional(), Length(max=120)])
    upi_payee_name = StringField("UPI Payee Name", validators=[Optional(), Length(max=120)])
