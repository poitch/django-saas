from captcha.fields import ReCaptchaField
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator, PasswordResetTokenGenerator
from django.http import HttpRequest
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from saas.mailer import send_multi_mail, AbstractSaasMailer

User = get_user_model()


class CreateUserForm(UserCreationForm):
    captcha = ReCaptchaField()

    class Meta:
        model = User
        fields = ("email", "password1", "password2", "captcha")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not email:
            raise ValidationError("This field is required.")
        if User.objects.filter(email=self.cleaned_data["email"]).count():
            raise ValidationError("Email is taken.")
        return self.cleaned_data["email"]

    def save(
        self,
        commit:bool=True,
        domain_override:str=None,
        subject_template_name:str="registration/activation_subject.txt",
        email_template_name:str="registration/activation_email.txt",
        use_https:bool=False,
        token_generator:PasswordResetTokenGenerator=default_token_generator,
        from_email:str=None,
        request:HttpRequest=None,
        html_email_template_name:str=None,
        extra_email_context:dict={},
        mailer:AbstractSaasMailer=None,
    ):
        user = super(CreateUserForm, self).save(commit=False)
        user.username = user.email
        user.is_active = False
        if commit:
            user.save()

        if mailer is not None:
            uid = urlsafe_base64_encode(force_bytes(user.id))
            token = token_generator.make_token(user)
            mailer.on_activating(request, user, uid, token)
        else:
            context = {
                "request": request,
                "protocol": 'https' if use_https else request.scheme,
                "username": self.cleaned_data.get("username"),
                "domain": domain_override if domain_override is not None else request.META["HTTP_HOST"],
                "uid": urlsafe_base64_encode(force_bytes(user.id)),
                "token": token_generator.make_token(user),
            } | extra_email_context
            send_multi_mail(
                subject_template_name,
                email_template_name,
                context,
                from_email,
                user.email,
                html_email_template_name=html_email_template_name,
            )

        return user
