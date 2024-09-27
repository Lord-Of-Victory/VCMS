from app import app

#-------------------------------------------------------------- App Run --------------------------------------------------#

if __name__=="__main__":
    create_admin()  # Creates admin When Database Is Created
    app.run(debug=False)    # Remove Debugging options When Deploying the Project
